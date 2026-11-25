from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_round


# Contexto de las escrituras internas de ``foreign_price``: ``write`` va directo
# a ``super`` y no vuelve a aplicar las reglas A/B (evita la recursión cuando el
# alterno calculado redondea a 0).
SKIP_FOREIGN_FILL = "l10n_ve_pos_skip_foreign_fill"


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")
    foreign_price = fields.Float(string="Foreign Price", digits=0)
    foreign_subtotal = fields.Float(string="Foreign Subtotal", digits=0)
    foreign_total = fields.Float(string="Foreign Total", digits=0)

    @api.model_create_multi
    def create(self, vals_list):
        """Completa en el servidor el ``foreign_price`` que el PdV no calculó.

        ``foreign_price`` solo lo fija el patch de ``l10n_ve_pos`` sobre
        ``setUnitPrice`` (frontend). Hay líneas que llegan sin pasar por él:

        * Líneas de una orden de venta liquidada en el PdV (``pos_sale``): desde
          el commit del core ``534aaac9114d`` su ``setUnitPrice`` asigna
          ``price_unit`` sin llamar a ``super`` cuando hay
          ``sale_order_line_id``, y el patch de ``l10n_ve_pos`` queda saltado
          (#16676).
        * Líneas de reembolso creadas por ``TicketScreen.onDoRefund`` (#15106).
        * Líneas de descuento global de ``pos_discount`` (#16547).

        Ese 0 se copia a la factura
        (``pos.order._get_invoice_lines_values``) y deja las líneas de producto
        en 0,00 en la moneda alterna. Aquí se repone con
        :meth:`_fill_missing_foreign_price`: nunca se cambia un precio alterno
        ya presente.
        """
        lines = super().create(vals_list)
        lines._sync_global_discount_foreign_price()
        lines._fill_missing_foreign_price()
        return lines

    def write(self, vals):
        """Mantiene ``foreign_price`` coherente al actualizar líneas (#16676).

        * Regla A: si la actualización trae ``price_unit`` o ``foreign_price``,
          las líneas que quedan con precio y sin alterno se completan con
          :meth:`_fill_missing_foreign_price`.
        * Regla B: si cambia ``price_unit`` y la actualización no trae un
          ``foreign_price`` distinto del guardado, se recalcula con
          :meth:`_get_foreign_price_from_price_unit`. Es el caso de una línea de
          orden de venta (``pos_sale``) ya sincronizada en borrador cuyo precio
          se edita: ``pos_sale`` cambia ``price_unit`` sin tocar
          ``foreign_price`` y el PdV manda el precio nuevo con el alterno viejo.
          Si la actualización trae un alterno distinto del guardado, se respeta.
        """
        if self.env.context.get(SKIP_FOREIGN_FILL):
            # Escritura interna de ``foreign_price``: sin reglas A/B.
            return super().write(vals)
        stale_lines = self.browse()
        if "price_unit" in vals:
            stale_lines = self._get_lines_with_stale_foreign_price(vals)
        res = super().write(vals)
        if {"price_unit", "foreign_price", "product_id", "order_id"} & vals.keys():
            self._sync_global_discount_foreign_price()
        if {"price_unit", "foreign_price"} & vals.keys():
            self._fill_missing_foreign_price()
        if stale_lines:
            stale_lines._recompute_foreign_price()
        return res

    def _get_lines_with_stale_foreign_price(self, vals):
        """Líneas cuyo precio cambia con ``vals`` sin un ``foreign_price`` nuevo."""
        env = self.env
        price_dp = env["decimal.precision"].precision_get("Product Price")
        foreign_dp = env["decimal.precision"].precision_get("Foreign Product Price")
        new_price = vals["price_unit"]
        stale = self.browse()
        for line in self:
            if not float_compare(line.price_unit, new_price, precision_digits=price_dp):
                continue
            if "foreign_price" in vals and float_compare(
                line.foreign_price, vals["foreign_price"], precision_digits=foreign_dp
            ):
                continue
            stale |= line
        return stale

    def _get_foreign_price_from_price_unit(self):
        """Precio unitario en la moneda alterna con el cálculo del PdV.

        * Caja en la moneda alterna y orden sin tasa: el precio unitario.
        * Si no: ``price_unit`` × tasa del PdV estampada en la orden
          (``pos.order.foreign_currency_rate``). Una línea que reembolsa otra
          (``refunded_orderline_id``) usa la tasa de la orden original, como
          ``_refundOriginalRate`` en el PdV; la línea de descuento global usa
          ``pos.order._get_payment_foreign_rate`` (#16547); cualquier otra línea,
          incl. una nueva en una orden de reembolso, la de su orden. NO es la tasa
          de la orden de venta (``sale.order``) ni la del día
          (``res.currency.rate``). Una caja en la moneda alterna estampa tasa 1,
          así que da el precio unitario.

        Redondeo HALF-UP a la precisión "Foreign Product Price" y con signo.
        Devuelve ``None`` si la orden no tiene tasa (y la caja no es alterna).
        Fórmula única compartida con el descuento global (#16547) y la factura
        (#16676).
        """
        self.ensure_one()
        order = self.order_id
        precision = self.env["decimal.precision"].precision_get("Foreign Product Price")
        original_order = self.refunded_orderline_id.order_id
        if original_order:
            rate = original_order.foreign_currency_rate or order.foreign_currency_rate
        elif self._is_global_discount_line():
            rate = order._get_payment_foreign_rate()
        else:
            rate = order.foreign_currency_rate
        if not rate:
            foreign_currency = order.config_id.foreign_currency_id
            if foreign_currency and order.currency_id == foreign_currency:
                return float_round(self.price_unit, precision_digits=precision)
            return None
        return float_round(self.price_unit * rate, precision_digits=precision)

    def _write_foreign_price(self, values_by_line):
        """Escribe ``foreign_price`` agrupado por valor y solo si cambia.

        Un alterno 0 producto del redondeo es válido: si la línea ya lo tiene no
        se escribe nada, y las escrituras van con ``SKIP_FOREIGN_FILL`` para no
        reentrar a las reglas A/B de ``write``.
        """
        precision = self.env["decimal.precision"].precision_get("Foreign Product Price")
        by_value = {}
        for line, value in values_by_line:
            if float_compare(line.foreign_price, value, precision_digits=precision):
                by_value.setdefault(value, self.browse())
                by_value[value] |= line
        for value, lines in by_value.items():
            lines.with_context(**{SKIP_FOREIGN_FILL: True}).write({"foreign_price": value})

    def _recompute_foreign_price(self):
        """Escribe el cálculo del PdV en las líneas (agrupado por valor)."""
        computed = [(line, line._get_foreign_price_from_price_unit()) for line in self]
        self._write_foreign_price([(line, value) for line, value in computed if value is not None])

    def _fill_missing_foreign_price(self):
        """Completa ``foreign_price`` en las líneas con precio y sin alterno.

        Primero copia el de la línea que se reembolsa (``refunded_orderline_id``,
        #15106: la NC revierte el USD congelado de la venta). Si sigue en 0,
        calcula con :meth:`_get_foreign_price_from_price_unit`, que en un
        reembolso usa la tasa de la venta original. Un alterno presente no se
        toca, ni una línea con precio 0 o sin tasa. Si el cálculo redondea a 0,
        la línea queda en 0,00 y es válido (#16676).
        """
        to_copy = []
        to_compute = self.browse()
        for line in self:
            if line.foreign_price or not line.price_unit:
                continue
            original = line.refunded_orderline_id
            if original and original.foreign_price:
                to_copy.append((line, original.foreign_price))
            else:
                to_compute |= line
        self._write_foreign_price(to_copy)
        to_compute._recompute_foreign_price()

    def _is_global_discount_line(self):
        """La línea es del producto de descuento global de ``pos_discount``.

        ``discount_product_id`` es un campo de ``pos_discount``, que no es
        dependencia de ``l10n_ve_pos``: en una base sin ``pos_discount``
        instalado, ``pos.config`` no lo tiene.
        """
        self.ensure_one()
        config = self.order_id.config_id
        if "discount_product_id" not in config._fields:
            return False
        discount_product = config.discount_product_id
        return bool(discount_product) and self.product_id == discount_product

    def _sync_global_discount_foreign_price(self):
        """Fija ``foreign_price`` de las líneas del descuento global a la tasa
        de la orden (ticket 16547).

        En el PdV, ``pos_discount`` crea esas líneas con precio negativo y, cada
        vez que cambia la orden, les reasigna ``price_unit`` directo, sin pasar
        por el ``setUnitPrice`` de ``l10n_ve_pos`` (única vía que calcula
        ``foreign_price`` en el frontend). Así la línea llegaba con
        ``foreign_price`` en 0 o con el de un monto anterior, y la factura
        (``pos.order._get_invoice_lines_values`` copia ``foreign_price`` a la
        línea contable) quedaba con el alterno sin descontar.

        El servidor manda: ``foreign_price = price_unit × tasa``, con la tasa
        del PdV estampada en la orden (``pos.order.foreign_currency_rate``) o,
        en un reembolso, la de la venta original (la misma que usan sus pagos,
        ver ``pos.order._get_payment_foreign_rate``), redondeado a la precisión
        "Foreign Product Price" como en el PdV. La fórmula es
        :meth:`_get_foreign_price_from_price_unit`. Las líneas que
        reembolsan otra línea (``refunded_orderline_id``) conservan el precio
        foráneo de la original.
        """
        precision = self.env["decimal.precision"].precision_get("Foreign Product Price")
        for line in self:
            if line.refunded_orderline_id or not line._is_global_discount_line():
                continue
            foreign_price = line._get_foreign_price_from_price_unit()
            if foreign_price is None:
                continue
            if float_compare(line.foreign_price, foreign_price, precision_digits=precision):
                line.with_context(**{SKIP_FOREIGN_FILL: True}).foreign_price = foreign_price

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
            if not line._is_global_discount_line():
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
