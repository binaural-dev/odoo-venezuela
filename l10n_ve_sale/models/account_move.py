import json
import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # Combo en factura directa
    # -------------------------------------------------------------------------

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids_combo(self):
        """Crea sublíneas y jerarquía del combo en memoria cuando el wizard
        deja una selección pendiente (`selected_combo_items`) en la factura.
        """
        # Líneas de tipo combo con configuración pendiente (aún son producto)
        combo_lines_pending = self.invoice_line_ids.filtered(
            lambda l: l.product_id.type == 'combo' and l.selected_combo_items
        )
        for line in combo_lines_pending:
            self._apply_multi_select_combo_items_invoice(line)
            # Tras _apply, la línea ya es line_section; se retaga abajo

        # Raíces de combo: secciones marcadas como combo_tagged
        combo_roots = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'line_section' and l.combo_tagged
        )
        for line in combo_roots:
            self._retag_combo_hierarchy_for_combo_line_invoice(line)

        self._cleanup_orphaned_combo_lines_invoice()

    def _apply_multi_select_combo_items_invoice(self, line):
        """Convierte la línea combo en sección raíz y crea subsecciones y
        productos elegidos (varios por opción), igual que en la orden de venta.
        """
        selected_combo_items = json.loads(line.selected_combo_items)
        if not selected_combo_items:
            return

        combo_item_model = self.env['product.combo.item']
        combo_ids = line.product_id.product_tmpl_id.sudo().combo_ids

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

        # Convertir la línea raíz a line_section (igual que SO→factura nativo)
        combo_name = line.product_id.display_name.upper()
        combo_qty = line.quantity

        # Borrar líneas hijo anteriores
        existing_children = self.invoice_line_ids.filtered(
            lambda l: l.combo_root_line_id == line
        )
        delete_commands = [Command.delete(l.id) for l in existing_children]

        # Convertir la raíz a sección
        root_update = Command.update(line.id, {
            'display_type': 'line_section',
            'name': combo_name,
            'product_id': False,
            'quantity': 0,
            'price_unit': 0.0,
            'combo_tagged': True,
        })

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
                    'combo_tagged': True,
                }))
                sequence_offset += 1
            for entry in entries:
                qty_multiplier = entry.get('quantity') or 1
                create_commands.append(Command.create({
                    'product_id': entry['product_id'],
                    'quantity': combo_qty * qty_multiplier,
                    'combo_item_qty_per_combo': qty_multiplier,
                    'sequence': line.sequence + sequence_offset,
                    'combo_tagged': True,
                }))
                sequence_offset += 1

        shift = sequence_offset - 1
        update_commands = [Command.update(
            inv_line.id,
            {'sequence': inv_line.sequence + shift},
        ) for inv_line in self.invoice_line_ids if inv_line.sequence > line.sequence and inv_line != line]

        line.selected_combo_items = False
        self.invoice_line_ids = [root_update] + delete_commands + create_commands + update_commands

    def _retag_combo_hierarchy_for_combo_line_invoice(self, combo_line):
        """Reasigna combo_parent_line_id/combo_root_line_id para las líneas de
        la factura que pertenecen al bloque del combo (raíz = line_section).
        """
        lines = self.invoice_line_ids.sorted('sequence')

        combo_line.combo_root_line_id = combo_line
        combo_line.combo_tagged = True

        current_subsection = self.env['account.move.line']
        in_block = False
        for ln in lines:
            if ln == combo_line:
                in_block = True
                current_subsection = self.env['account.move.line']
                continue
            if not in_block:
                continue

            # Otra line_section (no combo) cierra el bloque
            if ln.display_type == 'line_section' and not ln.combo_tagged:
                in_block = False
                continue

            # Subsección del combo
            is_combo_subsection = (
                ln.display_type == 'line_subsection'
                and (ln.combo_tagged or not ln.combo_root_line_id)
            )
            if is_combo_subsection:
                current_subsection = ln
                ln.combo_parent_line_id = combo_line
                ln.combo_root_line_id = combo_line
                ln.combo_tagged = True
                continue

            # Ítem producto del combo
            if ln.product_id and ln.combo_tagged:
                ln.combo_parent_line_id = current_subsection or combo_line
                ln.combo_root_line_id = combo_line
                continue

    def _cleanup_orphaned_combo_lines_invoice(self):
        """Limpia líneas de factura cuyo combo raíz (sección) ya no existe."""
        combo_roots = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'line_section' and l.combo_tagged
        )
        orphans = self.invoice_line_ids.filtered(
            lambda l: l.combo_root_line_id and l.combo_root_line_id not in combo_roots
        )
        if orphans:
            self.invoice_line_ids = [Command.delete(l.id) for l in orphans]

        remaining = self.invoice_line_ids - orphans
        empty_subsections = remaining.filtered(
            lambda l: l.display_type == 'line_subsection'
            and l.combo_root_line_id
            and not remaining.filtered(lambda c: c.combo_parent_line_id == l)
        )
        if empty_subsections:
            self.invoice_line_ids = [Command.delete(l.id) for l in empty_subsections]

    # -------------------------------------------------------------------------
    # Reconstrucción de jerarquía después de guardar (directo o desde SO)
    # -------------------------------------------------------------------------

    def _fix_combo_hierarchy_links_invoice(self):
        """Reconstruye combo_parent_line_id/combo_root_line_id con ids reales,
        de forma posicional o, si no hay secciones combo, desde sale_line_ids.
        """
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue

            lines = move.invoice_line_ids.sorted('sequence')

            # Raíces de combo: secciones marcadas con combo_tagged
            combo_roots = lines.filtered(
                lambda l: l.display_type == 'line_section' and l.combo_tagged
            )
            if combo_roots:
                self._fix_combo_hierarchy_positional_invoice(move, lines, combo_roots)
                continue

            # Sin secciones combo_tagged: intentar reconstruir desde sale_line_ids
            self._fix_combo_hierarchy_from_sale_invoice(move, lines)

    def _fix_combo_hierarchy_positional_invoice(self, move, lines, combo_roots):
        """Reconstrucción posicional: raíz = line_section con combo_tagged."""
        for combo_line in combo_roots:
            if combo_line.combo_root_line_id != combo_line:
                combo_line.write({'combo_root_line_id': combo_line.id, 'combo_tagged': True})

            current_subsection = self.env['account.move.line']
            in_block = False
            for ln in lines:
                if ln == combo_line:
                    in_block = True
                    current_subsection = self.env['account.move.line']
                    continue
                if not in_block:
                    continue

                # Otra sección sin combo_tagged cierra el bloque
                if ln.display_type == 'line_section' and not ln.combo_tagged:
                    in_block = False
                    continue

                is_combo_subsection = (
                    ln.display_type == 'line_subsection' and ln.combo_tagged
                )
                if is_combo_subsection:
                    current_subsection = ln
                    if ln.combo_parent_line_id != combo_line or ln.combo_root_line_id != combo_line:
                        ln.write({
                            'combo_parent_line_id': combo_line.id,
                            'combo_root_line_id': combo_line.id,
                        })
                    continue

                is_combo_item = ln.product_id and ln.combo_tagged
                if is_combo_item:
                    parent = current_subsection or combo_line
                    if ln.combo_parent_line_id != parent or ln.combo_root_line_id != combo_line:
                        ln.write({
                            'combo_parent_line_id': parent.id,
                            'combo_root_line_id': combo_line.id,
                        })
                    continue

    def _fix_combo_hierarchy_from_sale_invoice(self, move, lines):
        """Para facturas creadas desde una SO: mapea la jerarquía de
        sale.order.line a account.move.line vía sale_line_ids.
        """
        # Construir mapa sol.id -> inv_line
        sol_to_inv = {}
        for inv_line in lines:
            for sol in inv_line.sale_line_ids:
                sol_to_inv[sol.id] = inv_line

        for inv_line in lines:
            sols = inv_line.sale_line_ids
            if not sols:
                continue
            sol = sols[0]

            updates = {}
            if sol.combo_tagged and not inv_line.combo_tagged:
                updates['combo_tagged'] = True

            if sol.combo_root_line_id:
                root_inv = sol_to_inv.get(sol.combo_root_line_id.id)
                if root_inv and inv_line.combo_root_line_id != root_inv:
                    updates['combo_root_line_id'] = root_inv.id

            if sol.combo_parent_line_id:
                parent_inv = sol_to_inv.get(sol.combo_parent_line_id.id)
                if parent_inv and inv_line.combo_parent_line_id != parent_inv:
                    updates['combo_parent_line_id'] = parent_inv.id

            if updates:
                inv_line.write(updates)

    convert_currency_from_sale_order = fields.Boolean(
        related="company_id.convert_currency_from_sale_order",
    )

    def _get_sale_conversion_pricelist_rule(self, line):
        """Regla de tarifa que pisaria la conversion de esta linea, si la hay.

        `account_invoice_pricelist` (OCA) recalcula price_unit desde la tarifa
        de la factura, asi que si esa tarifa define una regla para el producto
        habria dos logicas compitiendo por el mismo campo. Este helper la
        detecta para poder abortar en vez de dejar que una pise a la otra.

        El acceso es defensivo: `pricelist_id` en account.move lo agrega
        `account_invoice_pricelist`, que no es dependencia de este modulo. Si
        no esta instalado no hay reglas que respetar y la conversion procede.
        """
        self.ensure_one()
        if "pricelist_id" not in self._fields:
            return False
        pricelist = self.pricelist_id
        if not pricelist or not line.product_id:
            return False
        return pricelist._get_product_rule(
            line.product_id,
            quantity=line.quantity or 1.0,
            uom=line.product_uom_id,
            date=self.invoice_date or fields.Date.context_today(self),
        )

    @api.onchange("currency_id", "invoice_date")
    def _onchange_currency_sync_from_so(self):
        """Convierte los precios unitarios desde el Pedido de Ventas cuando
        cambia la moneda o la fecha de la factura.

        Espejo de lo que hace binaural_purchase con la Orden de Compra, con la
        diferencia de que en ventas el enlace es `sale_line_ids`, un Many2many:
        una linea de factura puede proceder de varias lineas de venta. Solo se
        convierten las lineas con un origen inequivoco (exactamente una linea
        de venta); las agrupadas se dejan como estan porque no hay un precio
        de origen unico del que partir.

        La conversion usa la fecha de la factura, que en esta localizacion es
        la fecha de la tasa (la fecha visible del documento es
        invoice_date_display).
        """
        if not self.invoice_origin or not self.currency_id:
            return

        # No se compara contra _origin para decidir si hay algo que hacer: al
        # volver a la moneda de partida dentro del mismo borrador (USD -> VES
        # -> USD) el valor coincidiria con el guardado y se saldria sin
        # recalcular, dejando el precio de la otra moneda. El onchange solo se
        # dispara cuando cambia currency_id o invoice_date, asi que recalcular
        # siempre es correcto: si la moneda vuelve a ser la de la orden, la
        # primera rama restituye su precio original.
        # Solo facturas de cliente. Las notas de credito y debito se emiten
        # siempre en base a su factura de origen, asi que recalcularlas desde
        # el pedido de ventas las desalinearia del documento que rectifican.
        if not (
            self.move_type == "out_invoice"
            and self.company_id.convert_currency_from_sale_order
        ):
            return

        invoice_date = self.invoice_date or fields.Date.context_today(self)
        precision = self.env["decimal.precision"].precision_get("Product Price")

        # Primero se validan todas las lineas: si alguna tiene regla de tarifa
        # no se convierte ninguna, para no dejar la factura a medio recalcular.
        blocking = []
        for line in self.invoice_line_ids:
            if len(line.sale_line_ids) != 1:
                continue
            if line.product_id.type not in ("consu", "service"):
                continue
            if self._get_sale_conversion_pricelist_rule(line):
                blocking.append(line.product_id.display_name)

        if blocking:
            # dict.fromkeys en vez de set(): con lineas duplicadas del mismo
            # producto (mismo precio y cantidad, cada una con su propia
            # sale_line_ids), el mismo nombre podia agregarse mas de una vez
            # y el mensaje de error repetia el producto. dict.fromkeys quita
            # los duplicados preservando el orden de aparicion.
            blocking = list(dict.fromkeys(blocking))
            raise UserError(
                _(
                    "The pricelist %(pricelist)s defines a rule for the "
                    "following products, so their price cannot be recalculated "
                    "from the sale order: %(products)s.\n\n"
                    "Both mechanisms set the same unit price and one would "
                    "override the other. Either remove the pricelist rule or "
                    "disable \"Convert Currency From Sale Order\".",
                    pricelist=self.pricelist_id.display_name,
                    products=", ".join(blocking),
                )
            )

        for line in self.invoice_line_ids:
            if len(line.sale_line_ids) != 1:
                continue

            so_line = line.sale_line_ids
            if line.product_id.type not in ("consu", "service"):
                continue

            order = so_line.order_id

            if self.currency_id == order.currency_id:
                # Misma moneda que la orden: no hay nada que convertir, la
                # fecha no interviene.
                new_price_unit = so_line.price_unit
            else:
                # Cualquier otra moneda -- incluida la alterna de la
                # compania -- convierte con invoice_date, la fecha de LA
                # FACTURA. No se usa so_line.foreign_price aqui a proposito:
                # ese campo esta calculado con la fecha de la ORDEN
                # (order.foreign_rate_date), que puede no coincidir con
                # invoice_date -- convert_currency_from_sale_order es un flag
                # independiente de use_invoice_rate_from_sale_order, asi que
                # la factura puede tener su propia fecha. El ticket pide
                # convertir "a la tasa de la Factura", no a la de la orden.
                new_price_unit = float_round(
                    order.currency_id._convert(
                        so_line.price_unit,
                        self.currency_id,
                        self.company_id,
                        invoice_date,
                        round=False,
                    ),
                    precision_digits=precision,
                )

            # Solo se toca price_unit: foreign_price es un campo calculado que
            # depende de el y de la fecha, asi que se recalcula solo.
            line.price_unit = new_price_unit
