from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")
    foreign_price = fields.Float(string="Foreign Price", digits=0)
    foreign_subtotal = fields.Float(string="Foreign Subtotal", digits=0)
    foreign_total = fields.Float(string="Foreign Total", digits=0)

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 19 replacement for the Odoo 17 ``_export_for_ui``
        hook (removed in commit ``2a5f1abf2e98 [IMP] pos_*: refactoring
        with related models part 2``).

        We extend the base Odoo 19 field list with the Venezuelan
        foreign-currency contract. ``foreign_currency_rate`` is a
        related field on the order header, but it MUST be listed
        here too so the read-back payload exposes it on every line
        (the frontend computes per-line values from it).
        """
        res = super()._load_pos_data_fields(config) or []
        for name in (
            "foreign_price",
            "foreign_subtotal",
            "foreign_total",
            "foreign_currency_rate",
        ):
            if name not in res:
                res.append(name)
        return res

    @api.constrains("qty", "refunded_orderline_id", "order_id")
    def _check_qty_not_negative_outside_refund(self):
        """Solo las líneas de reembolso pueden tener cantidad negativa.

        Refuerzo en servidor del guard del PdV
        (``static/src/overrides/models/pos_order_line.js``, ``setQuantity``):
        el frontend impide teclear una cantidad negativa, pero el sync del
        PdV y el backend escriben ``qty`` directamente, así que una orden de
        venta con línea negativa (que en VE emitiría una factura fiscal con
        cantidad negativa en vez de una nota de crédito) todavía podría
        colarse por RPC o por edición manual del pedido.

        Exenciones — deben ser las mismas que en el frontend:

        * ``refunded_orderline_id``: línea de reembolso real, creada por
          ``TicketScreen.onDoRefund`` / ``pos.order.line._prepare_refund_data``
          con ``qty = -(qty - refunded_qty)``.
        * ``order_id.is_refund``: orden marcada como reembolso por el core
          (``pos.order.refund`` fija ``is_refund=True``); cubre las líneas
          hijas de combo de un reembolso y cualquier línea añadida por el
          core a una orden de reembolso.
        * ``order_id.preset_id.is_return``: preset "Return mode" nativo, donde
          el core fuerza ``-Math.abs(qty)`` en TODAS las líneas del carrito.
        """
        precision = self.env["decimal.precision"].precision_get("Product Unit")
        for line in self:
            if float_compare(line.qty, 0.0, precision_digits=precision) >= 0:
                continue
            if line.refunded_orderline_id:
                continue
            order = line.order_id
            if order.is_refund or order.preset_id.is_return:
                continue
            raise ValidationError(
                _(
                    "Negative quantity is only allowed on refund lines. "
                    'Product "%(product)s" has a quantity of %(qty)s in order '
                    "%(order)s. To return products, use the refund flow from "
                    "the orders screen instead of a negative quantity.",
                    product=line.full_product_name or line.product_id.display_name,
                    qty=line.qty,
                    order=order.name or order.pos_reference or "",
                )
            )

    def _prepare_refund_data(self, refund_order, PosPackOperationLot):
        """Odoo 19 keeps this hook; we just inject ``foreign_price``
        so the refund line preserves the Venezuelan contract (refund
        flow is the only path that recreates order lines from a
        source order and would otherwise drop the value).
        """
        res = super()._prepare_refund_data(refund_order, PosPackOperationLot)
        res["foreign_price"] = self.foreign_price
        return res
