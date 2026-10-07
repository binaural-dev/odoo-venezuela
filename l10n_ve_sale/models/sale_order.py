import datetime
import json
import logging
from collections import defaultdict

from lxml import etree
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "filter.partner.mixin"]

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.foreign_currency_id.id or False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    vat = fields.Char(
        string="VAT",
        help="VAT of the partner",
        compute="_compute_vat",
        readonly=False,
    )

    @api.onchange('order_line')
    def _onchange_order_line(self):
        combo_lines_pending = self.order_line.filtered(
            lambda l: l.product_template_id.type == 'combo' and l.selected_combo_items
        )
        for line in combo_lines_pending:
            self._apply_multi_select_combo_items(line)

        super()._onchange_order_line()

        combo_lines = self.order_line.filtered(
            lambda l: l.product_template_id.type == 'combo'
        )
        for line in combo_lines:
            self._retag_combo_hierarchy_for_combo_line(line)
            self._quarantine_stray_lines_from_combo(line)

        self._cleanup_orphaned_combo_lines()

    def _apply_multi_select_combo_items(self, line):
        """Extiende la creación nativa de líneas de combo para admitir varias
        elecciones por opción, agrupadas en una subsección decorativa por opción
        cuando el combo tiene más de una.
        """
        selected_combo_items = json.loads(line.selected_combo_items)
        if not selected_combo_items:
            return

        combo_item_model = self.env['product.combo.item']
        combo_ids = line.product_template_id.sudo().combo_ids

        by_combo = defaultdict(list)
        for entry in selected_combo_items:
            combo_item = combo_item_model.browse(entry['combo_item_id'])
            by_combo[combo_item.combo_id.id].append(entry)

        missing = combo_ids.filtered(lambda c: c.id not in by_combo)
        if missing:
            raise ValidationError(_(
                "Debe seleccionar al menos un producto para cada opción del "
                "combo: %s"
            ) % ", ".join(missing.mapped('name')))

        combo_item_lines = line._get_linked_lines().filtered('combo_item_id')
        delete_commands = [Command.delete(l.id) for l in combo_item_lines]

        create_commands = []
        sequence_offset = 1
        multi_option = len(combo_ids) > 1
        for combo in combo_ids:
            entries = by_combo.get(combo.id) or []
            if multi_option:
                create_commands.append(Command.create({
                    'display_type': 'line_subsection',
                    'name': combo.name.upper(),
                    'sequence': line.sequence + sequence_offset,
                    # combo_tagged desde la creación: super()._onchange_order_line
                    # promueve line_subsection→line_section cuando no hay parent_id,
                    # y _retag revierte eso solo si ya está marcada como combo.
                    'combo_tagged': True,
                }))
                sequence_offset += 1
            for entry in entries:
                qty_multiplier = entry.get('quantity') or 1
                create_commands.append(Command.create({
                    'product_id': entry['product_id'],
                    'product_uom_qty': line.product_uom_qty * qty_multiplier,
                    'combo_item_qty_per_combo': qty_multiplier,
                    'combo_item_id': entry['combo_item_id'],
                    'product_no_variant_attribute_value_ids': [
                        Command.set(entry['no_variant_attribute_value_ids'])
                    ],
                    'product_custom_attribute_value_ids': [Command.clear()] + [
                        Command.create(attribute_value)
                        for attribute_value in entry['product_custom_attribute_values']
                    ],
                    'sequence': line.sequence + sequence_offset,
                    'linked_line_id': line.id if line._origin else False,
                    'linked_virtual_id': line.virtual_id if not line._origin else False,
                }))
                sequence_offset += 1

        shift = sequence_offset - 1
        update_commands = [Command.update(
            order_line.id,
            {'sequence': order_line.sequence + shift},
        ) for order_line in self.order_line if order_line.sequence > line.sequence]

        line.selected_combo_items = False
        self.order_line = delete_commands + create_commands + update_commands

    def _retag_combo_hierarchy_for_combo_line(self, combo_line):
        """Reasigna combo_parent_line_id/combo_root_line_id por posición dentro
        del bloque del combo y revierte la promoción nativa de
        `line_subsection` a `line_section`.
        """
        combo_ids = combo_line.product_template_id.sudo().combo_ids.ids
        lines = self.order_line.sorted('sequence')

        combo_line.combo_root_line_id = combo_line
        combo_line.combo_tagged = True

        current_subsection = self.env['sale.order.line']
        in_block = False
        for ln in lines:
            if ln == combo_line:
                in_block = True
                current_subsection = self.env['sale.order.line']
                continue
            if not in_block:
                continue

            if ln.product_template_id.type == 'combo':
                in_block = False
                continue

            is_combo_header = (
                not ln.product_id
                and not ln.combo_item_id
                and ln.combo_tagged
                and ln.display_type in ('line_section', 'line_subsection')
            )
            if is_combo_header:
                if ln.display_type != 'line_subsection':
                    ln.display_type = 'line_subsection'
                current_subsection = ln
                ln.combo_parent_line_id = combo_line
                ln.combo_root_line_id = combo_line
                ln.combo_tagged = True
                continue

            is_native_combo_item = bool(
                ln.combo_item_id and ln.combo_item_id.combo_id.id in combo_ids
            )
            added_via_subsection_kebab = (
                not is_native_combo_item
                and ln.product_id
                and ln.combo_added_via_subsection_kebab
            )

            if is_native_combo_item or added_via_subsection_kebab:
                ln.combo_parent_line_id = current_subsection or combo_line
                ln.combo_root_line_id = combo_line
                ln.combo_tagged = True
                # Tanto los ítems nativos del wizard como los agregados por
                # el kebab de la subsección escalan con la cantidad del
                # combo padre: si el combo se pide 2 veces, cada producto
                # de adentro también se duplica (multiplicador *
                # cantidad del combo), nunca se iguala sin más a la
                # cantidad del combo (eso es justo lo que hace el core por
                # su cuenta -- ver `sale.order_line._onchange_order_line`,
                # rama `elif combo_item_lines and ...` -- y lo pisa acá,
                # después de correr `super()`).
                ln.product_uom_qty = (
                    combo_line.product_uom_qty * (ln.combo_item_qty_per_combo or 1.0)
                )
                continue

            if ln.display_type in ('line_section', 'line_subsection'):
                # Una sección/subsección AJENA de verdad sí cierra el
                # bloque del combo -- pero un producto suelto (el caso de
                # abajo) no debería, porque entonces cualquier cosa que
                # venga DESPUÉS en la lista (p.ej. "lol" y sus hijos, si el
                # producto ajeno quedó posicionado antes) dejaría de
                # re-etiquetarse esta ronda y perdería su marca -- eso es
                # justo lo que pasaba con los "productos opcionales" del
                # configurador nativo, que se insertan en medio del árbol.
                in_block = False
                continue

            # Producto suelto, ajeno al combo: no se toca, pero tampoco
            # corta el recorrido -- se sigue buscando el resto del árbol
            # más adelante en la lista.
            continue

    def _quarantine_stray_lines_from_combo(self, combo_line):
        """Reubica al final del árbol, bajo "Productos Adicionales", los productos
        ajenos al combo que quedaron intercalados (detección por posición en el
        array, no por `sequence`).
        """
        tree = self.order_line.filtered(
            lambda l: l == combo_line or l.combo_root_line_id == combo_line
        )
        if len(tree) <= 1:
            return

        order_lines = list(self.order_line)
        if combo_line not in order_lines:
            return
        root_index = order_lines.index(combo_line)
        last_tree_index = max(i for i, ln in enumerate(order_lines) if ln in tree)

        strays = self.env['sale.order.line']
        for ln in order_lines[root_index + 1:last_tree_index + 1]:
            if (
                ln.product_id
                and ln not in tree
                and not ln.combo_tagged
                and ln.product_template_id.type != 'combo'
            ):
                strays |= ln

        if not strays:
            return

        separator_name = _("Productos Adicionales")
        existing_separator = self.env['sale.order.line']
        if last_tree_index + 1 < len(order_lines):
            candidate = order_lines[last_tree_index + 1]
            if (
                candidate not in strays
                and candidate.display_type == 'line_section'
                and candidate.name == separator_name
            ):
                existing_separator = candidate

        insertion_point = max(tree.mapped('sequence')) + 1
        shift = len(strays) + (0 if existing_separator else 1)
        shift_commands = [
            Command.update(ln.id, {'sequence': ln.sequence + shift})
            for ln in self.order_line
            if ln not in strays and ln != existing_separator and ln.sequence >= insertion_point
        ]

        next_sequence = insertion_point
        separator_commands = []
        if existing_separator:
            separator_commands.append(
                Command.update(existing_separator.id, {'sequence': next_sequence})
            )
        else:
            separator_commands.append(Command.create({
                'display_type': 'line_section',
                'name': separator_name,
                'sequence': next_sequence,
            }))
        next_sequence += 1

        stray_commands = []
        for stray in strays.sorted('sequence'):
            stray_commands.append(Command.update(stray.id, {'sequence': next_sequence}))
            next_sequence += 1

        self.order_line = shift_commands + separator_commands + stray_commands

    def _cleanup_orphaned_combo_lines(self):
        """Elimina subsecciones sin hijos y la raíz del combo cuando se queda sin
        ningún descendiente.
        """
        combo_roots = self.order_line.filtered(
            lambda l: l.product_template_id.type == 'combo'
        )

        # OJO: solo se chequea que la RAÍZ siga presente -- no que el padre
        # directo (subsección) también lo esté. Ese segundo chequeo se
        # intentó agregar y causó una falsa alarma real: si el retag de
        # este ciclo se corta antes de llegar a una subsección (p.ej. por
        # una línea en blanco recién insertada por el kebab, que todavía no
        # es ni cabecera ni ítem de combo), esa subsección no se re-etiqueta
        # ESTE ciclo, pero su `combo_parent_line_id`/`combo_root_line_id`
        # siguen siendo válidos de ciclos anteriores -- no hay nada roto de
        # verdad, y borrarla ahí fue un falso positivo que se llevó una
        # subsección entera (con sus hijos) sin que el usuario tocara nada.
        orphans = self.order_line.filtered(
            lambda l: l.combo_root_line_id and l.combo_root_line_id not in combo_roots
        )
        if orphans:
            self.order_line = [Command.delete(l.id) for l in orphans]

        remaining = self.order_line - orphans
        empty_subsections = remaining.filtered(
            lambda l: l.display_type == 'line_subsection'
            and l.combo_root_line_id
            and not remaining.filtered(lambda c: c.combo_parent_line_id == l)
        )
        if empty_subsections:
            self.order_line = [Command.delete(l.id) for l in empty_subsections]

        remaining = remaining - empty_subsections
        emptied_roots = combo_roots.filtered(
            lambda r: r in remaining
            and (r._origin or r.virtual_id)
            and not r.selected_combo_items
            and not remaining.filtered(lambda c: c.id != r.id and c.combo_root_line_id == r)
        )
        if emptied_roots:
            self.order_line = [Command.delete(r.id) for r in emptied_roots]

    def default_rate(self):
        """
        This method is used to get the rate of the payment.

        Returns
        -------
        type = float
            The rate of the payment
        """
        rate_values = self.env["res.currency.rate"].compute_rate(
            self.env.company.foreign_currency_id.id or self.env.ref("base.VEF").id,
            self.date_order or fields.Date.today(),
        )
        return rate_values.get("foreign_rate", 0)

    def default_inverse_rate(self):
        """
        This method is used to get the inverse rate of the payment.

        Returns
        -------
        type = float
            The inverse rate of the payment
        """
        rate_values = self.env["res.currency.rate"].compute_rate(
            self.env.company.foreign_currency_id.id or self.env.ref("base.VEF").id,
            self.date_order or fields.Date.today(),
        )
        return rate_values.get("foreign_inverse_rate", 0)

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        compute="_compute_rate",
        default=default_rate,
        digits="Tasa",
        store=True,
        readonly=False,
        tracking=True,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=default_inverse_rate,
        store=True,
        readonly=False,
    )

    last_foreign_rate = fields.Float(copy=False)
    manually_set_rate = fields.Boolean(default=False)

    foreign_rate_date = fields.Date(
        string="Foreign rate date",
        compute="_compute_rate",
        store=True,
        readonly=False,
        copy=False,
        # Mismo criterio que el default de foreign_rate (default_rate, que
        # resuelve con fields.Date.today()): al crear la orden el ORM aplica
        # los defaults y no ejecuta _compute_rate, asi que sin este default el
        # campo nacería vacío y la fecha no coincidiría con la tasa.
        default=lambda self: fields.Date.context_today(self),
        help=(
            "Date whose exchange rate is used for this order's alternate "
            "currency amounts. It is not date_order: the core rewrites "
            "date_order with the confirmation date, and when the rate is "
            "frozen ('Update sale order rate using date order' disabled) this "
            "field keeps the date the rate was actually taken from. It is the "
            "date passed to the invoice so both convert with the same rate."
        ),
    )

    total_taxed = fields.Many2one(
        "account.tax",
        help="Total Taxed of the invoice",
    )

    foreign_taxable_income = fields.Monetary(
        help="Foreign Taxable Income of the invoice",
        compute="_compute_foreign_taxable_income",
        currency_field="foreign_currency_id",
    )

    foreign_total_billed = fields.Monetary(
        help="Foreign Total Billed of the invoice",
        compute="_compute_foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
    )
    foreign_untaxed_total = fields.Monetary(string="foreign untaxed total", currency_field="foreign_currency_id", store=True, 
                                            compute='_compute_foreign_untaxed_total' )

    pricelist_id = fields.Many2one(
        domain=lambda self: (
            "[('company_id', 'in', (company_id, False))]"
        )
    )

    address = fields.Char(related="partner_id.street")

    mobile = fields.Char(related="partner_id.mobile")

    amount_untaxed_total_signed = fields.Monetary(
        string="Total Untaxed Signed",
        compute="_compute_amount_signed",
        currency_field="company_currency_id",
        store=True,
    )

    amount_total_signed = fields.Monetary(
        string="Total Signed",
        compute="_compute_amount_signed",
        currency_field="company_currency_id",
        store=True,
    )
    
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
    )
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **kwargs):
        if 'load' in kwargs:
            del kwargs['load']
        context = self.with_context(active_test=False)
        return super(SaleOrder, context).search_read(
            domain, fields, offset, limit, order
        )

    @api.constrains("order_line")
    def _check_taxes_id(self):
        for order in self:
            for line in order.order_line:
                if (
                    len(line.tax_ids) != 1
                    and not line.display_type
                    and self.env.company.unique_tax
                ):
                    raise ValidationError(_("All products must contain only one tax."))

    @api.constrains("order_line", "state")
    def _check_lines_maximum_limit(self):
        are_sale_lines_limited = self.env.company.are_sale_lines_limited

        if not are_sale_lines_limited:
            return

        maximum_sales_line_limit = self.env.company.maximum_sales_line_limit

        if not maximum_sales_line_limit:
            return

        for order in self:

            if order.state in ["draft", "cancel"]:
                continue

            if len(order.order_line) <= maximum_sales_line_limit:
                continue

            raise UserError(
                _("The order line limit must not exceed %s.", maximum_sales_line_limit)
            )

    @api.depends("tax_totals")
    def _compute_foreign_taxable_income(self):
        """
        Compute the foreign taxable income of the order
        """
        for move in self:
            move.foreign_taxable_income = False
            if move.order_line:
                move.foreign_taxable_income = move.tax_totals.get(
                    "base_amount_foreign_currency", 0
                )

    @api.depends("tax_totals", "currency_id", "date_order", "amount_total")
    def _compute_foreign_total_billed(self):
        """
        Compute the foreign total billed of the order
        """
        for order in self:
            order.foreign_total_billed = False
            if not order.order_line or not order.tax_totals:
                continue
            # Una sola via: tax_totals ya trae el total convertido a la moneda
            # alterna, incluso si la orden esta en una tercera moneda, porque
            # se arma desde el foreign_price de cada linea.
            order.foreign_total_billed = order.tax_totals.get(
                "total_amount_foreign_currency", 0
            )

    @api.depends("tax_totals", "currency_id", "date_order", "amount_untaxed")
    def _compute_foreign_untaxed_total(self):
        """
        Compute the foreign untaxed total of the order
        """
        for order in self:
            order.foreign_untaxed_total = False
            if not order.order_line or not order.tax_totals:
                continue
            # Una sola via: base_amount_foreign_currency se arma desde el
            # foreign_price de cada linea, que ya viene convertido a la moneda
            # alterna sea cual sea la moneda del documento.
            order.foreign_untaxed_total = order.tax_totals.get(
                "base_amount_foreign_currency", 0
            )

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """
        This method is used to get the view of the account move form and add the foreign currency
        symbol to the page title.

        Parameters
        ----------
        view_id : int
            The id of the view

        view_type : str
            The type of the view

        options : dict
            The options of the view

        Returns
        -------
        type = dict
            The view of the account move form with the foreign currency symbol added to the page title
        """
        foreign_currency_symbol = ""
        foreign_currency_id = self.env.company.foreign_currency_id
        res = super().get_view(view_id, view_type, **options)

        if foreign_currency_id:
            foreign_currency_symbol = foreign_currency_id.symbol
            foreign_currency_name = foreign_currency_id.name
            company_currency_id = self.env.company.currency_id
            company_currency_symbol = company_currency_id.symbol or ""
            if view_type == "form":
                view_id = self.env.ref(
                    "l10n_ve_sale.view_sale_order_form_l10n_ve_sales"
                ).id
                doc = etree.XML(res["arch"])
                foreign_price_order_line = doc.xpath("//notebook/page/field[@name='order_line']/list/field[@name='foreign_price']")
                if foreign_price_order_line:
                    foreign_price_order_line[0].set("string", _("Price") + " " + foreign_currency_name)
                foreign_subtotal_order_line = doc.xpath("//notebook/page/field[@name='order_line']/list/field[@name='foreign_subtotal']")
                if foreign_subtotal_order_line:
                    foreign_subtotal_order_line[0].set("string", _("Subtotal") + " " + foreign_currency_name)
                page = doc.xpath("//page[@name='foreign_currency']")
                if page:
                    page[0].set(
                        "string", _("Foreign Currency ") + foreign_currency_symbol
                    )
                res["arch"] = etree.tostring(doc, encoding="unicode")
            elif view_type == "list":
                doc = etree.XML(res["arch"])
                foreign_total_billed = doc.xpath("//field[@name='foreign_total_billed']")
                if foreign_total_billed:
                    foreign_total_billed[0].set("string", _("Total") + " " + foreign_currency_name)
                
                foreign_untaxed_total = doc.xpath("//field[@name='foreign_untaxed_total']")
                if foreign_untaxed_total:
                    foreign_untaxed_total[0].set("string", _("Untaxed Total") + " " + foreign_currency_name)

                total_signed = doc.xpath("//field[@name='amount_total_signed']")
                if total_signed:
                    total_signed[0].set("string", _("Total") + " " + company_currency_symbol)
                
                untaxed_total_signed = doc.xpath("//field[@name='amount_untaxed_total_signed']")
                if untaxed_total_signed:
                    untaxed_total_signed[0].set("string", _("Untaxed Total") + " " + company_currency_symbol)
                
                res["arch"] = etree.tostring(doc, encoding="unicode")
            elif view_type == "pivot":
                _logger.warning("Pivot view")
                doc = etree.XML(res["arch"])
                foreign_total_billed = doc.xpath("//field[@name='foreign_total_billed']")
                if foreign_total_billed:
                    foreign_total_billed[0].set("string", _("Total") + " " + foreign_currency_name)
                
                foreign_untaxed_total = doc.xpath("//field[@name='foreign_untaxed_total']")
                if foreign_untaxed_total:
                    foreign_untaxed_total[0].set("string", _("Untaxed Total") + " " + foreign_currency_name)

                total_signed = doc.xpath("//field[@name='amount_total_signed']")
                if total_signed:
                    total_signed[0].set("string", _("Total") + " " + company_currency_symbol)
                
                untaxed_total_signed = doc.xpath("//field[@name='amount_untaxed_total_signed']")
                if untaxed_total_signed:
                    untaxed_total_signed[0].set("string", _("Untaxed Total") + " " + company_currency_symbol)
                
                res["arch"] = etree.tostring(doc, encoding="unicode")
                
        return res

    @api.depends(
        "order_line.price_subtotal",
        "currency_id",
        "company_id",
        "payment_term_id",
        "foreign_rate",
    )
    def _compute_tax_totals(self):
        """Delegates straight to `super()`, without the per-record
        `with_context(active_id=..., active_model=...)` this used to set
        before iterating -- `with_context()` builds a new `Environment`
        for every order (walking the transaction's live environment
        registry), which in this project (with very deep `super()`
        chains) is one of several spots that could end in a real
        `RecursionError` -- see `account.move._compute_tax_totals`
        (`l10n_ve_accountant/models/account_move.py`), where the same
        per-record context injection was found to cause exactly that
        while reconciling payments.

        `account_tax._get_tax_totals_summary` (`l10n_ve_accountant`)
        derives `record` (the order) FIRST from
        `base_lines[0]['record'].order_id` -- `base_lines` here comes
        from the core's own `_compute_tax_totals`
        (`sale/models/sale_order.py`), which builds each base line via
        `line._prepare_base_line_for_taxes_computation()`; that method
        (core, unmodified in this project) always sets `'record'` to the
        `sale.order.line` itself, so `record.order_id` resolves to this
        order without needing `active_id`/`active_model` at all. The
        context is only a fallback for the (untested-here) case where
        `base_lines` is empty.

        The `@api.depends` above is kept (needed for `foreign_rate`,
        specific to this project) but the call itself is delegated
        directly, with no per-record context."""
        super()._compute_tax_totals()

    @api.depends("partner_id", "partner_id.vat", "partner_id.prefix_vat")
    def _compute_vat(self):
        """
        Compute the vat of the partner and add the prefix to it if it exists in the partner record
        """
        for rec in self:
            vat = ""

            if not rec.partner_id:
                rec.vat = vat
                continue

            if rec.partner_id.prefix_vat and rec.partner_id.vat:
                vat = (rec.partner_id.prefix_vat or "") + (rec.partner_id.vat or "")
            else:
                vat = rec.partner_id.vat or ""
            rec.vat = vat.upper()

    @api.onchange("name")
    def _onchange_name(self):
        """
        Ensure the foreign_rate and foreign_inverse_rate are computed when the order is still not
        created.
        """
        self._compute_rate()

    @api.depends("foreign_currency_id", "date_order")
    def _compute_rate(self):
        """
        Compute the rate of the sale order using the compute_rate method of the res.currency.rate
        model.
        """
        Rate = self.env["res.currency.rate"]
        # If the user doesn't want to update the foreign rate using the date order, then don't
        # compute the rate when it is not zero.
        for sale in self:
            # date_order es Datetime: si viene vacio, .date() reventaria antes
            # de llegar al or, asi que se comprueba primero.
            rate_date = sale.date_order.date() if sale.date_order else fields.Date.today()

            # TODO(website): confirmar con el responsable de la vertical de
            # website/e-commerce si esta condicion sigue siendo necesaria y si
            # el comportamiento (congelar la tasa de ordenes con website_id)
            # es el correcto. No se toca en la tarea 80063; queda como
            # oportunidad de analisis para otro momento.
            if (
                sale.manually_set_rate
                or "website_id" in sale._fields
                and sale.website_id
            ):
                # La tasa viene fijada de fuera; se deja constancia de la fecha
                # solo si aun no hay ninguna, para no pisar la original.
                if not sale.foreign_rate_date:
                    sale.foreign_rate_date = rate_date
                continue
            company = sale.company_id or self.env.company
            if (
                not company.update_sale_order_rate_using_date_order
                and not float_is_zero(
                    sale.foreign_rate,
                    precision_rounding=company.currency_id.rounding,
                )
            ):
                # Tasa congelada: no se recalcula. La fecha se sella la primera
                # vez (la orden nace con el default de foreign_rate, tomado en
                # ese momento) y a partir de ahi no se toca, aunque el core
                # mueva date_order al confirmar.
                if not sale.foreign_rate_date:
                    sale.foreign_rate_date = rate_date
                continue
            rate_values = Rate.compute_rate(sale.foreign_currency_id.id, rate_date)
            sale.foreign_rate = rate_values.get("foreign_rate", 0)
            sale.foreign_inverse_rate = rate_values.get("foreign_inverse_rate", 0)
            # La tasa se recalculo: la fecha acompana al valor nuevo.
            sale.foreign_rate_date = rate_date

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        for sale in self:
            base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
                "base.USD", raise_if_not_found=False
            )
            if not bool(sale.foreign_rate):
                return
            sale.foreign_inverse_rate = (
                1 / sale.foreign_rate
                if sale.foreign_currency_id.id == base_usd_id
                else sale.foreign_rate
            )

    def _get_invoiceable_lines(self, final=False):
        if self._context.get("ignore_limit", False):
            return super()._get_invoiceable_lines(final)

        res = super()._get_invoiceable_lines(final)
        limit = self.company_id.max_product_invoice

        if len(res) <= limit:
            return res
        return res[:limit]

    def _create_invoices(self, grouped=False, final=False, date=None):
        """Crea las facturas de la orden (varias si excede el límite de líneas),
        envía la tasa de la orden y reconstruye la jerarquía de combo en la factura.
        """
        invoices = self.env["account.move"]
        for order in self:
            invoiceable_lines = order._get_invoiceable_lines(final)
            while len(invoiceable_lines) != 0:
                new_invoices = super()._create_invoices(grouped, final, date)
                invoices |= new_invoices
                new_invoices._fix_combo_hierarchy_links_invoice()
                invoiceable_lines = order._get_invoiceable_lines(final)

        return invoices

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        company = self.company_id or self.env.company
        invoice_vals["manually_set_rate"] = (
            self.manually_set_rate or company.use_invoice_rate_from_sale_order
        )
        invoice_vals["foreign_rate"] = self.foreign_rate
        invoice_vals["foreign_inverse_rate"] = self.foreign_inverse_rate

        if company.use_invoice_rate_from_sale_order:
            # En esta localizacion invoice_date es la fecha de la TASA; la
            # fecha visible del documento (y la que determina la fecha
            # contable) es invoice_date_display -- ver
            # account.move._get_accounting_date_source.
            #
            # Se pasa foreign_rate_date, no date_order: el core reescribe
            # date_order con la fecha de confirmacion, mientras que
            # foreign_rate_date conserva la fecha de la que realmente salio la
            # tasa (incluso si quedo congelada). Asi la factura convierte con
            # la misma tasa que la orden, via _convert(), sin heredar el rate.
            rate_date = self.foreign_rate_date or (
                self.date_order.date() if self.date_order else False
            )
            if rate_date:
                invoice_vals["invoice_date"] = rate_date

        return invoice_vals

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._fix_combo_hierarchy_links()
        for sale in res:
            Rate = self.env["res.currency.rate"]
            rate_values = Rate.compute_rate(
                sale.foreign_currency_id.id,
                sale.date_order or fields.Date.today(),
            )
            last_foreign_rate = rate_values.get("foreign_rate", 0)
            if sale.manually_set_rate and sale.foreign_rate != last_foreign_rate:
                sale.message_post(
                    body=_(
                        "The rate has been updated from %(last_rate)s to %(rate)s ",
                    )
                    % ({"rate": sale.foreign_rate, "last_rate": last_foreign_rate})
                )
        return res

    def write(self, vals):
        if vals.get("foreign_rate", False):
            vals.update({"last_foreign_rate": self.foreign_rate})
        res = super().write(vals)
        if "order_line" in vals:
            self._fix_combo_hierarchy_links()
        if (
            vals.get("foreign_rate", False)
            and self.manually_set_rate
            and self.foreign_rate != self.last_foreign_rate
        ):
            self.message_post(
                body=_(
                    "The rate has been updated from %(last_rate)s to %(rate)s ",
                )
                % ({"rate": self.foreign_rate, "last_rate": self.last_foreign_rate})
            )
        return res

    def _fix_combo_hierarchy_links(self):
        """Reconstruye combo_parent_line_id/combo_root_line_id con ids reales
        después de guardar (un Many2one entre líneas nuevas del mismo lote no
        persiste bien desde el onchange).
        """
        for order in self:
            lines = order.order_line.sorted('sequence')
            combo_roots = lines.filtered(
                lambda l: l.product_template_id.type == 'combo'
            )
            for combo_line in combo_roots:
                combo_ids = combo_line.product_template_id.sudo().combo_ids.ids
                if combo_line.combo_root_line_id != combo_line:
                    combo_line.write({'combo_root_line_id': combo_line.id})

                current_subsection = self.env['sale.order.line']
                in_block = False
                for ln in lines:
                    if ln == combo_line:
                        in_block = True
                        current_subsection = self.env['sale.order.line']
                        continue
                    if not in_block:
                        continue

                    if ln.product_template_id.type == 'combo':
                        in_block = False
                        continue

                    is_combo_header = (
                        not ln.product_id
                        and not ln.combo_item_id
                        and ln.combo_tagged
                        and ln.display_type == 'line_subsection'
                    )
                    if is_combo_header:
                        current_subsection = ln
                        if (
                            ln.combo_parent_line_id != combo_line
                            or ln.combo_root_line_id != combo_line
                        ):
                            ln.write({
                                'combo_parent_line_id': combo_line.id,
                                'combo_root_line_id': combo_line.id,
                            })
                        continue

                    is_native_combo_item = bool(
                        ln.combo_item_id and ln.combo_item_id.combo_id.id in combo_ids
                    )
                    adopted = (
                        not is_native_combo_item
                        and ln.product_id
                        and ln.combo_added_via_subsection_kebab
                    )
                    if is_native_combo_item or adopted:
                        parent = current_subsection or combo_line
                        if (
                            ln.combo_parent_line_id != parent
                            or ln.combo_root_line_id != combo_line
                        ):
                            ln.write({
                                'combo_parent_line_id': parent.id,
                                'combo_root_line_id': combo_line.id,
                            })
                        continue

                    if ln.display_type in ('line_section', 'line_subsection'):
                        in_block = False
                    continue

    @api.onchange("pricelist_id")
    def _onchange_pricelist_id(self):
        """
        Recalculate the prices of the products in the purchase order when the rate changes.
        """
        try:
            record = self if isinstance(self.id, int) else self._origin
            record._recompute_prices()
            if self.pricelist_id:
                record.message_post(
                    body=_(
                        "Product prices have been recomputed according to pricelist %s.",
                        self.pricelist_id._get_html_link(),
                    )
                )
        except Exception:
            self._recompute_prices()

    def _block_valid_confirm(self):
        self.ensure_one()

        block_order_invoice_payment_state = (
            self.company_id.block_order_invoice_payment_state
        )
        block_order_invoice_total_amount_overdue = (
            self.company_id.block_order_invoice_total_amount_overdue
        )

        today_date = fields.Date.today()

        invoice_ids = self.env["account.move"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("amount_total", ">", 0),
                "|",
                ("payment_state", "=", block_order_invoice_payment_state),
                ("invoice_date_due", "<", today_date),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted")
            ]
        )

        if not any(invoice_ids):
            return None

        invoice_count_payment_state = 0
        invoice_count_date_expired = 0
        amount_total_overdue = 0
        amount_total_not_pay = 0

        for invoice_id in invoice_ids:
            if block_order_invoice_payment_state:
                if invoice_id.payment_state == block_order_invoice_payment_state:
                    invoice_count_payment_state += 1

            if invoice_id.invoice_date_due and invoice_id.invoice_date_due < today_date:
                amount_total_overdue += invoice_id.amount_total
                amount_total_not_pay += invoice_id.amount_residual
                invoice_count_date_expired += 1

        if invoice_count_payment_state:
            payment_state_labels = {
                "not_paid": _("Not Paid"),
                "in_payment": _(
                    "In Payment Process",
                ),
            }

            raise UserError(
                _("The budget cannot be confirmed. You have %s Invoices (%s).")
                % (
                    invoice_count_payment_state,
                    payment_state_labels[block_order_invoice_payment_state],
                )
            )

        if block_order_invoice_total_amount_overdue:
            if amount_total_not_pay > block_order_invoice_total_amount_overdue:
                raise UserError(
                    _(
                        "The budget cannot be confirmed. Has an overdue amount of (%.2f) that cannot be greater than %.2f %s."
                    )
                    % (
                        amount_total_not_pay,
                        block_order_invoice_total_amount_overdue,
                        invoice_id.currency_id.name,
                    )
                )

    def action_confirm(self):
        skip_not_allow_sell_products_validation = self.env.context.get(
            "skip_not_allow_sell_products_validation", False
        )
        for order in self:
            # Validación de líneas de producto
            if not order.order_line or all(line.display_type for line in order.order_line):
                raise UserError(_("Before confirming an order, you need to add a product."))

            # Validación de productos no permitidos para la venta y límite de crédito
            if self.env.company.not_allow_sell_products and not skip_not_allow_sell_products_validation:
                for line in order.order_line:
                    if (
                        line.product_id.is_storable
                        and line.product_id.type == "consu"
                        and line.product_id.qty_available < line.product_uom_qty
                    ):
                        msg = _("Does not have enough units available for the product ")
                        msg += _("{}. Only has {} units of the {} demanded.").format(
                            line.product_id.name,
                            line.product_id.qty_available,
                            line.product_uom_qty,
                        )
                        raise ValidationError(msg)
            

                if (
                    order.company_id.account_use_credit_limit
                    and order.partner_id.use_partner_credit_limit_order
                ):
                    total_pay = order.partner_id.credit + order.amount_total
                    if total_pay > order.partner_id.credit_limit:
                        decimal_places = order.currency_id.decimal_places
                        raise ValidationError(
                            _(
                                "No se ha confirmado el presupuesto. Límite de crédito excedido. La cuenta por cobrar del cliente es de %s más %s en presupuesto da un total de %s superando el límite de ventas de %s. Por favor cancele el presupuesto o comuníquese con el administrador para aumentar el límite de crédito del cliente.",
                                round(order.partner_id.credit, decimal_places),
                                round(order.amount_total, decimal_places),
                                round(total_pay, decimal_places),
                                round(order.partner_id.credit_limit, decimal_places),
                            )
                        )

                    order._block_valid_confirm()

            # A la confirmacion (accion explicita del usuario, no un compute
            # automatico) le corresponde reaccionar de una vez a la falta de
            # tasa, en vez de dejar pasar la orden con foreign_rate en 0 en
            # silencio -- exactamente el punto de entrada que el docstring de
            # compute_rate() reserva para raise_if_not_found=True.
            if (
                order.foreign_currency_id
                and not order.manually_set_rate
                and float_is_zero(order.foreign_rate, precision_rounding=order.currency_id.rounding)
            ):
                rate_date = order.date_order.date() if order.date_order else fields.Date.today()
                self.env["res.currency.rate"].compute_rate(
                    order.foreign_currency_id.id, rate_date, raise_if_not_found=True
                )

        res = super().action_confirm()
        for sale in self:
            picking = sale.picking_ids
            if not picking:
                continue
            product_limit = sale.company_id.limit_product_qty_out
            if product_limit <= 0:
                continue
            picking_moves = picking.move_ids
            if not picking_moves:
                continue
            picking_vals = picking.read(['location_dest_id', 'location_id', 'move_type', 'picking_type_id'])
            if not picking_vals:
                continue
            picking_vals = {
                key: (value[0] if isinstance(value, tuple) else value)
                for key, value in picking_vals[0].items()
            }
            picking_vals['origin'] = picking.origin
            picking_vals['partner_id'] = picking.partner_id.id
            picking_vals['user_id'] = picking.user_id.id
            list_pickings_moves = [picking_moves[i:i + product_limit] for i in range(0, len(picking_moves), product_limit)]
            picking.move_ids = list_pickings_moves[0]
            for list_moves in list_pickings_moves[1:]:
                picking_vals["move_ids"] = list_moves
                self.env['stock.picking'].create(picking_vals)
        return res

    def cancel_order_after_date(self):
        orders = self.search(
            [
                ("create_date", "<", fields.Date.today() - datetime.timedelta(days=1)),
                ("state", "not in", ["sale", "done", "cancel"]),
            ]
        )
        for order in orders:
            order.action_cancel()

    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_amounts(self):
        for order in self:
            order.amount_untaxed = order.tax_totals['base_amount_currency']
            order.amount_tax = order.tax_totals['tax_amount_currency']
            order.amount_total = order.tax_totals['total_amount_currency']

   

    @api.depends("tax_totals", "amount_untaxed", "amount_total")
    def _compute_amount_signed(self):
        """Totales en moneda de la compania.

        Se leen de tax_totals en vez de volver a convertir con _convert(): el
        motor de impuestos ya hizo esa conversion al calcular los totales del
        documento, y las claves sin sufijo "_currency" vienen justamente en
        moneda de compania (las que lo llevan estan en la moneda del
        documento). Convertir por segunda vez abre una via paralela que puede
        diferir por redondeo.
        """
        for order in self:
            tax_totals = order.tax_totals if isinstance(order.tax_totals, dict) else {}
            order.amount_untaxed_total_signed = tax_totals.get(
                "base_amount", order.amount_untaxed
            )
            order.amount_total_signed = tax_totals.get(
                "total_amount", order.amount_total
            )

    invoice_status = fields.Selection(
        selection_add=[('partially_billed', 'Partially billed')],
    )

    @api.depends('state', 'order_line.invoice_status', 'order_line.qty_invoiced', 'order_line.product_uom_qty')
    def _compute_invoice_status(self):
        sale_done_orders = self.filtered(lambda order: order.state in ('sale', 'done'))
        other_orders = self - sale_done_orders

        if sale_done_orders:
            super(SaleOrder, sale_done_orders)._compute_invoice_status()

        if other_orders:
            super(SaleOrder, other_orders)._compute_invoice_status()

        for order in sale_done_orders:
            invoiceable_lines = order.order_line.filtered(lambda line: not line.display_type)
            total_invoiced = sum(invoiceable_lines.mapped('qty_invoiced'))
            total_invoiceable = sum(
                line.product_uom_qty
                if line.product_id.invoice_policy == 'order'
                else line.qty_delivered
                for line in invoiceable_lines
            )

            if total_invoiced > 0 and total_invoiced < total_invoiceable:
                order.invoice_status = 'partially_billed'

        for order in other_orders:
            order.invoice_status = order.invoice_status
