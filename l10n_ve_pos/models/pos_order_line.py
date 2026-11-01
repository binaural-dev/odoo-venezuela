from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")
    foreign_price = fields.Float(string="Foreign Price", digits=0)
    foreign_subtotal = fields.Float(string="Foreign Subtotal", digits=0)
    foreign_total = fields.Float(string="Foreign Total", digits=0)

    @api.model_create_multi
    def create(self, vals_list):
        """Rellena ``foreign_price`` en las líneas de reembolso creadas desde el PdV.

        El flujo de reembolso de Odoo 19 (``TicketScreen.onDoRefund``) crea la
        línea destino con un ``create`` directo del core que NO pasa por el
        override JS ``setUnitPrice`` (única vía que fija ``foreign_price`` en el
        frontend), así que la línea se sincroniza con ``foreign_price = 0``. Ese
        0 se propaga al asiento de la nota de crédito
        (``pos.order._get_invoice_lines_values`` copia ``foreign_price`` a la
        línea contable) y deja los productos en 0,00 en la moneda alterna, con
        toda la NC descuadrada en USD.

        Reponemos el precio unitario foráneo desde la línea original que se
        reembolsa (``refunded_orderline_id``), de modo que la NC revierta
        EXACTAMENTE el monto en USD congelado de la factura de origen —a la tasa
        del día de la venta, no a la del día del reembolso— (ticket #15106).
        No sobrescribimos un ``foreign_price`` ya presente (p. ej. el que inyecta
        ``_prepare_refund_data`` en el reembolso de backend).
        """
        lines = super().create(vals_list)
        for line in lines:
            original = line.refunded_orderline_id
            if original and not line.foreign_price and original.foreign_price:
                line.foreign_price = original.foreign_price
        return lines

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

    @api.constrains("price_unit", "product_id", "order_id")
    def _check_discount_price_not_positive(self):
        """La línea del producto de descuento no puede quedar con precio
        positivo (Ticket 14352).

        Refuerzo en servidor del guard del PdV
        (``static/src/overrides/models/pos_order_line.js``, ``setUnitPrice``):
        el frontend fuerza el precio a negativo, pero hay caminos del propio
        core que escriben ``price_unit`` directamente sin pasar por
        ``setUnitPrice`` (``pos_discount`` al aplicar el descuento global,
        y el long-press de ``OrderSummary`` sobre una línea), así que el
        guard de JS solo no es suficiente.

        Exenciones — idénticas a ``_check_qty_not_negative_outside_refund``:

        * ``refunded_orderline_id``: línea de reembolso real.
        * ``order_id.is_refund``: orden marcada como reembolso por el core.
        * ``order_id.preset_id.is_return``: preset "Return mode" nativo.
        """
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            order = line.order_id
            config = order.config_id
            # `discount_product_id` is a `pos_discount` field, not a
            # `l10n_ve_pos` dependency: on a DB without `pos_discount`
            # installed, `pos.config` doesn't have it at all.
            if "discount_product_id" not in config._fields:
                continue
            discount_product = config.discount_product_id
            if not discount_product or line.product_id != discount_product:
                continue
            if float_compare(line.price_unit, 0.0, precision_digits=precision) <= 0:
                continue
            if line.refunded_orderline_id:
                continue
            if order.is_refund or order.preset_id.is_return:
                continue
            raise ValidationError(
                _(
                    "Discount line price cannot be positive. Product "
                    '"%(product)s" has a price of %(price)s in order '
                    "%(order)s.",
                    product=line.product_id.display_name,
                    price=line.price_unit,
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
