from odoo import api, fields, models, _
from odoo.fields import Command
from odoo.tools import float_round
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    foreign_currency_id = fields.Many2one(
        related="order_id.foreign_currency_id", store=True
    )
    foreign_rate = fields.Float(related="order_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(
        related="order_id.foreign_inverse_rate", store=True
    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Foreign Product Price",
        store=True,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )

    invoiced = fields.Boolean(compute="_compute_invoiced", store=True, copy=False)

    combo_parent_line_id = fields.Many2one(
        'sale.order.line',
        string="Sección / Subsección Padre",
        # OJO: NO 'cascade'. Si el padre es un registro ya guardado (real)
        # y se borra, `ondelete='cascade'` hace que el propio ORM intente
        # encontrar y hacer unlink() de TODO lo que apunte a él -- incluso
        # líneas todavía sin guardar (`NewId`), que nunca existieron en la
        # base y no se les puede hacer un DELETE real (revienta con
        # `invalid input syntax for type integer: "virtual_N"`). El
        # borrado en cascada ya lo manejamos nosotros mismos en Python
        # (ver `unlink()` acá abajo y la limpieza de huérfanos en
        # sale_order.py); 'set null' es la salida segura para lo que la
        # BD intente hacer sola.
        ondelete='set null',
        index=True
    )
    combo_root_line_id = fields.Many2one(
        'sale.order.line',
        string="Contenedor Combo Raíz",
        ondelete='set null',
        index=True
    )
    combo_item_qty_per_combo = fields.Float(
        string="Cantidad elegida por combo",
        default=1.0,
        help=(
            "Unidades de este producto elegidas en el wizard por cada "
            "unidad del combo. Se usa para recalcular product_uom_qty en "
            "cada onchange, porque el core sobreescribe la cantidad de "
            "todas las líneas de combo para igualarla a la del combo "
            "padre cada vez que vuelve a correr su propio onchange."
        ),
    )
    combo_added_via_subsection_kebab = fields.Boolean(
        string="Agregado desde el kebab de una subsección de combo",
        default=False,
        help=(
            "Marca puesta en create() cuando la línea se creó vía el "
            "kebab 'Agregar un producto' de una sección/subsección que "
            "pertenece a un combo (ver combo_section_kebab_context.js). "
            "No se puede distinguir esto de un producto agregado por el "
            "botón global al pie de la lista solo por posición/secuencia "
            "-- cuando el combo es lo último de la orden, ambos caminos "
            "producen exactamente el mismo resultado posicional -- así "
            "que se marca explícitamente desde el propio contexto de la "
            "acción en vez de adivinarlo después."
        ),
    )
    combo_tagged = fields.Boolean(
        string="Pertenece a un combo",
        default=False,
        help=(
            "Espejo booleano de `combo_root_line_id`/`combo_parent_line_id` "
            "(ver `_retag_combo_hierarchy_for_combo_line`). Existe porque "
            "el JS del subtotal de sección (`combo_section_subtotal.js`) "
            "necesita saber si una línea pertenece a un combo ANTES de "
            "guardar la orden, y un Many2one que apunta a otra línea "
            "también sin guardar (`NewId`) no llega resuelto de forma "
            "confiable a `record.data` del lado cliente -- un booleano "
            "simple sí viaja bien sin importar el estado de guardado."
        ),
    )

    # override
    @api.depends("product_id", "product_uom_id", "product_uom_qty","order_id.currency_id")
    def _compute_price_unit(self):
        def has_manual_price(line):
            # `line.currency_id` can be False for NewId records
            currency = (
                line.currency_id or
                line.order_id.currency_id
                or line.company_id.currency_id
                or line.env.company.currency_id
            )
            return currency.compare_amounts(line.technical_price_unit, line.price_unit)

        force_recompute = self.env.context.get('force_price_recomputation')
        for line in self:
            # Don't compute the price for deleted lines or lines for which the
            # price unit doesn't come from the product.
            if not line.order_id or line.is_downpayment or line._is_global_discount():
                continue

            # check if the price has been manually set or there is already invoiced amount.
            # if so, the price shouldn't change as it might have been manually edited.
            if (
                (not force_recompute and has_manual_price(line))
                or line.qty_invoiced > 0
                or (line.product_id.expense_policy == 'cost' and line.is_expense)
            ):
                continue
            line = line.with_context(sale_write_from_compute=True)
            if not line.product_uom_id or not line.product_id:
                line.price_unit = 0.0
                line.technical_price_unit = 0.0
            else:
                line._reset_price_unit()
    @api.depends("invoice_lines.move_id.state", "invoice_lines.quantity")
    def _compute_invoiced(self):
        for line in self:
            invoice_lines = line._get_invoice_lines()
            invoiced = invoice_lines and all(
                invoice_line.move_id.move_type == "out_invoice"
                for invoice_line in invoice_lines
            )
            line.invoiced = invoiced

    @api.depends(
        "price_unit",
        "order_id.date_order",
        "order_id.foreign_rate_date",
        "currency_id",
        "company_id",
    )
    def _compute_foreign_price(self):
        for line in self:

            # foreign_rate_date es la fecha de la que salio la tasa de la orden
            # y sobrevive a que el core reescriba date_order al confirmar. Sin
            # esto la linea se recalculaba con la fecha de confirmacion aunque
            # la tasa de la orden estuviera congelada.
            order_date = (
                line.order_id.foreign_rate_date
                or line.order_id.date_order
                or fields.Date.today()
            )

            company_currency = line.company_id.currency_id
            foreign_currency = line.company_id.foreign_currency_id
            line_currency = line.currency_id or line.order_id.currency_id or line.company_id.currency_id

            if not line_currency or not foreign_currency:
                line.foreign_price = 0.0
                continue

            if line_currency.id == foreign_currency.id:
                line.foreign_price = line.price_unit
                continue

            # round=False + redondeo a la precision del campo: _convert()
            # redondea por defecto a los decimales de la moneda destino
            # (USD = 2), pero foreign_price usa "Foreign Product Price",
            # cuya precision es configurable.
            # Sin esto un precio unitario pequeño se pierde al convertir, y
            # el valor de la orden no coincide con el de la factura que sale
            # de ella (account.move.line usa el mismo criterio).
            precision = self.env["decimal.precision"].precision_get(
                "Foreign Product Price"
            )
            line.foreign_price = float_round(
                line_currency._convert(
                    line.price_unit,
                    foreign_currency,
                    line.company_id,
                    order_date,
                    round=False,
                ),
                precision_digits=precision,
            )

    @api.depends("product_uom_qty", "foreign_price", "discount", "tax_ids")
    def _compute_foreign_subtotal(self):
        """Subtotal en moneda alterna.

        Mismo criterio que account.move.line: cuando hay impuestos se pasa por
        compute_all para que el subtotal sea la base real (descuenta el
        impuesto si va incluido en el precio) y quede redondeado a la moneda
        alterna. Sin impuestos es la multiplicacion directa.
        """
        for line in self:
            line_discount_price_unit = line.foreign_price * (
                1 - (line.discount / 100.0)
            )
            foreign_subtotal = line_discount_price_unit * line.product_uom_qty

            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.product_uom_qty,
                    currency=line.foreign_currency_id,
                    product=line.product_id,
                    partner=line.order_id.partner_id,
                )
                line.foreign_subtotal = taxes_res["total_excluded"]
            else:
                line.foreign_subtotal = foreign_subtotal

    
    def _prepare_foreign_base_line_for_taxes_computation(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._prepare_foreign_base_line_for_taxes_computation(
            self,
            price_unit=self.foreign_price,
            tax_ids=self.tax_ids,
            quantity=self.product_uom_qty,
            partner_id=self.order_id.partner_id,
            currency_id=self.order_id.currency_id or self.order_id.company_id.currency_id,
            rate=getattr(self.order_id, 'currency_rate', 1.0),
        )

    @api.onchange('combo_parent_line_id')
    def _onchange_combo_parent_line_id(self):
        if self.combo_parent_line_id:
            if self.combo_parent_line_id.combo_root_line_id:
                self.combo_root_line_id = self.combo_parent_line_id.combo_root_line_id
            else:
                self.combo_root_line_id = self.combo_parent_line_id

    def unlink(self):
        # El webclient a veces manda un Command.delete apuntando a un id
        # virtual (p.ej. "virtual_155") que nunca llegó a guardarse en la
        # base -- un combo creado y borrado dentro de la misma sesión sin
        # guardar, reconciliado de más por el propio one2many del
        # navegador. `browse()` no valida el tipo de id, así que ese
        # recordset puede traer ese string mezclado con ids reales; el
        # primer intento de leer CUALQUIER campo (acá `combo_parent_line_id`)
        # dispara un SELECT ... WHERE id IN (...) que Postgres rechaza
        # (`invalid input syntax for type integer`). Se descarta antes de
        # tocar nada: no hay nada real que borrar para un id así.
        valid_ids = [i for i in self.ids if isinstance(i, int)]
        if len(valid_ids) != len(self.ids):
            self = self.browse(valid_ids)
        if not self:
            return True

        parents_to_check = self.mapped('combo_parent_line_id').filtered(
            lambda l: l.display_type in ('line_section', 'line_subsection')
        )
        roots_to_check = self.mapped('combo_root_line_id').filtered(
            lambda l: l.product_id.type == 'combo'
        )
        res = super(SaleOrderLine, self).unlink()

        # Si una subsección o sección queda sin productos hijos, se elimina automáticamente
        for parent in parents_to_check:
            if parent.exists():
                has_children = self.search_count([('combo_parent_line_id', '=', parent.id)])
                if not has_children:
                    if parent.combo_root_line_id.product_id.type == 'combo':
                        roots_to_check |= parent.combo_root_line_id
                    parent.unlink()

        # Si la línea real del combo se quedó sin ningún descendiente (ni
        # subsecciones ni productos), tampoco tiene sentido dejarla sola.
        for root in roots_to_check:
            if root.exists():
                has_descendants = self.search_count([('combo_root_line_id', '=', root.id)])
                if not has_descendants:
                    root.unlink()

        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Marca como parte del combo las líneas creadas desde el kebab de una
        subsección para que no se descarten al guardar.
        """
        if self.env.context.get('combo_added_via_subsection_kebab'):
            for vals in vals_list:
                if not vals.get('display_type') and not vals.get('combo_item_id'):
                    vals['combo_added_via_subsection_kebab'] = True
        lines = super().create(vals_list)
        return lines

    def _prepare_invoice_line(self, **optional_values):
        """Propaga las marcas de combo a la línea de factura y deja el nombre
        de raíz, secciones y subsecciones en MAYÚSCULAS (sin el "x {qty}" nativo).
        """
        self.ensure_one()

        res = super()._prepare_invoice_line(**optional_values)

        # El core nativo genera '{nombre} x {qty}' para el combo raíz:
        # se reemplaza por solo el nombre del producto en MAYÚSCULAS.
        if self.product_id.type == 'combo':
            res['name'] = self.product_id.display_name.upper()

        if self.combo_tagged:
            res['combo_tagged'] = True
            if res.get('display_type') in ('line_section', 'line_subsection'):
                res['name'] = (res.get('name') or self.name or '').upper()

        if self.combo_item_qty_per_combo and self.combo_item_qty_per_combo != 1.0:
            res['combo_item_qty_per_combo'] = self.combo_item_qty_per_combo

        return res

    def _get_combo_item_display_price(self):
        """Reparte el precio del combo por item_type: fixed_price conserva su
        lst_price, percentage toma un % del resto y principal reparte lo que sobra
        por línea, absorbiendo el residuo de redondeo.
        """
        self.ensure_one()

        combo_line = self._get_linked_line()
        if not combo_line:
            return super()._get_combo_item_display_price()

        combo_product_price = combo_line._get_display_price_ignore_combo()

        sibling_lines = self.order_id.order_line.filtered(
            lambda l: l.combo_item_id and l._get_linked_line() == combo_line
        )

        line_prices = {}

        for line in sibling_lines:
            if line.combo_item_id.item_type == 'fixed_price':
                fixed_price = line.combo_item_id.currency_id._convert(
                    from_amount=line.combo_item_id.lst_price,
                    to_currency=self.currency_id,
                    company=self.company_id,
                    date=self.order_id.date_order or fields.Date.today(),
                )
                line_prices[line] = self.currency_id.round(fixed_price)

        total_fixed = sum(line_prices.values()) if line_prices else 0
        remain_after_fixed = combo_product_price - total_fixed

        total_percentage = 0.0
        for line in sibling_lines:
            if line.combo_item_id.item_type == 'percentage':
                pct_amount = remain_after_fixed * (line.combo_item_id.percentage / 100.0)
                pct_amount_rounded = self.currency_id.round(pct_amount)
                line_prices[line] = pct_amount_rounded
                total_percentage += pct_amount_rounded

        remain_for_principal = remain_after_fixed - total_percentage

        principal_lines = sibling_lines.filtered(lambda l: l.combo_item_id.item_type == 'principal')
        if principal_lines:
            avg_principal_price = self.currency_id.round(remain_for_principal / len(principal_lines))
            for p_line in principal_lines:
                line_prices[p_line] = avg_principal_price

            total_calculated = sum(line_prices.values())
            delta = combo_product_price - total_calculated
            if delta:
                line_prices[principal_lines[-1]] += delta
        else:
            total_calculated = sum(line_prices.values())
            delta = combo_product_price - total_calculated
            if delta and sibling_lines:
                line_prices[sibling_lines[-1]] = line_prices.get(sibling_lines[-1], 0.0) + delta

        return line_prices.get(self, 0.0)