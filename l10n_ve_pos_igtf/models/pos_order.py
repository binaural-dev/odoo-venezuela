from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_round


class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float()
    bi_igtf = fields.Float()

    # NO declarar igtf_amount / bi_igtf en _load_pos_data_fields: eso los
    # convierte en campos REACTIVOS del modelo JS, y update_igtf() los escribe
    # (incluso desde PosOrder.setup()). Cada escritura marca el registro
    # `_dirty`, lo que dispara el ciclo de sincronización/render del POS y
    # cuelga el navegador en un bucle. Se envían al backend desde
    # `PosOrder.serializeForORM` (order_model.js), que solo corre al sincronizar.

    def _get_total_with_igtf(self):
        """Total efectivo que el cliente debe pagar.

        ``amount_total`` es el total de la factura y NUNCA incluye el IGTF (el
        recargo no es un impuesto de línea; se factura aparte contra
        ``customer_account_igtf_id``). En cambio ``amount_paid`` sí lo incluye,
        porque el frontend fija ``pos.payment.amount = base + IGTF`` en las
        líneas con ``apply_igtf``.

        ``igtf_amount`` es un campo firmado (negativo en reembolsos), así que
        la suma vale igual para notas de crédito.
        """
        self.ensure_one()
        return self.currency_id.round(self.amount_total + self.igtf_amount)

    def action_pos_order_paid(self):
        self.ensure_one()

        if self.currency_id.is_zero(self.igtf_amount):
            return super().action_pos_order_paid()

        # Copia deliberada de point_of_sale/models/pos_order.py::
        # action_pos_order_paid (Odoo 20). El core compara amount_total contra
        # amount_paid con su propia lógica inline y no expone ningún hook
        # factorizado (_get_rounded_amount / _is_pos_order_paid NO participan),
        # así que la única forma de comparar contra el total CON IGTF es
        # replicar el método. Las órdenes sin IGTF delegan en super() arriba,
        # de modo que un cambio del core solo puede afectar a esta rama.
        # REVISAR EN CADA UPGRADE.
        total_with_igtf = self._get_total_with_igtf()

        if not self.config_id.cash_rounding \
           or self.config_id.only_round_cash_method \
           and not any(p.payment_method_id.type == "cash" for p in self.payment_ids):
            total = total_with_igtf
        else:
            total = float_round(
                total_with_igtf,
                precision_rounding=self.config_id.rounding_method.rounding,
                rounding_method=self.config_id.rounding_method.rounding_method,
            )

        isPaid = float_is_zero(
            total - self.amount_paid, precision_rounding=self.currency_id.rounding
        )

        if not isPaid and not self.config_id.cash_rounding:
            raise UserError(_("Order %s is not fully paid.", self.name))
        elif not isPaid and self.config_id.cash_rounding:
            currency = self.currency_id
            if self.config_id.rounding_method.rounding_method == "HALF-UP":
                maxDiff = currency.round(self.config_id.rounding_method.rounding / 2)
            else:
                maxDiff = currency.round(self.config_id.rounding_method.rounding)

            diff = currency.round(total_with_igtf - self.amount_paid)
            if not abs(diff) <= maxDiff:
                raise UserError(_("Order %s is not fully paid.", self.name))

        self.write({"state": "paid"})

        return True

    def _is_pos_order_paid(self):
        # Usado por el asistente de pago desde backend (wizard/pos_payment.py).
        # Mismo criterio que action_pos_order_paid: el cliente debe cubrir el
        # total de la factura más el IGTF.
        if self.currency_id.is_zero(self.igtf_amount):
            return super()._is_pos_order_paid()

        amount_total = self._get_total_with_igtf()
        if float_is_zero(
            self.refunded_order_id.amount_total + amount_total,
            precision_rounding=self.currency_id.rounding,
        ):
            amount_total = -self.refunded_order_id.amount_paid
        return float_is_zero(
            self._get_rounded_amount(amount_total) - self.amount_paid,
            precision_rounding=self.currency_id.rounding,
        )

    @api.model
    def get_refund_igtf_data(self, order_ids):
        """IGTF that the original orders of a refund can still give back.

        A refund gives back the IGTF the customer paid on the sale, in
        proportion to what it refunds, whatever methods it is paid with: the
        PoS computes its share from the amounts returned here
        (``l10n_ve_pos_igtf`` order_model.js, ``_igtfRefundShare``). Each
        amount is what the original order charged minus what its previous
        refunds already gave back, so successive partial refunds add up to the
        IGTF of the sale and the last one takes the exact remainder. A refund
        of several orders takes, of each, the part of its lines that refunds
        that order.

        Returns one dict per original order, with positive amounts: ``id``,
        ``amount_total`` (invoice total still to refund), ``igtf_amount``,
        ``bi_igtf`` and ``foreign_igtf_amount`` (IGTF in the alternate currency).
        """
        if not order_ids:
            return []
        if isinstance(order_ids, int):
            order_ids = [order_ids]
        result = []
        for order in self.browse(order_ids).exists():
            result.append(order._get_refund_igtf_remaining())
        return result

    def _get_refund_igtf_remaining(self):
        self.ensure_one()
        currency = self.currency_id
        foreign_currency = self.company_id.foreign_currency_id or currency
        charged = {
            "amount_total": abs(self.amount_total),
            "igtf_amount": abs(self.igtf_amount),
            "bi_igtf": abs(self.bi_igtf),
            "foreign_igtf_amount": abs(
                sum(self.payment_ids.filtered("include_igtf").mapped("foreign_igtf_amount"))
            ),
        }
        refunded = dict.fromkeys(charged, 0.0)
        refund_lines = self.lines.refund_orderline_ids.filtered(
            lambda line: line.order_id.state not in ("draft", "cancel")
        )
        for refund in refund_lines.order_id:
            lines = refund_lines.filtered(lambda line: line.order_id == refund)
            amount = abs(sum(lines.mapped("price_subtotal_incl")))
            share = amount / abs(refund.amount_total) if refund.amount_total else 0.0
            refund_igtf = refund.payment_ids.filtered("include_igtf")
            refunded["amount_total"] += amount
            refunded["igtf_amount"] += abs(refund.igtf_amount) * share
            refunded["bi_igtf"] += abs(refund.bi_igtf) * share
            refunded["foreign_igtf_amount"] += (
                abs(sum(refund_igtf.mapped("foreign_igtf_amount"))) * share
            )
        remaining = {"id": self.id}
        for key, value in charged.items():
            rounding = foreign_currency if key == "foreign_igtf_amount" else currency
            remaining[key] = max(rounding.round(value - refunded[key]), 0.0)
        return remaining

    def _prepare_account_move_line_data_for_payments(self, partner=None):
        """Add the IGTF of the payments each entry groups to its metadata and,
        on an invoice, take it out of its ``payment_term`` line.

        The payments of an order that pays IGTF add up to the invoice total
        plus the IGTF (``pos.payment.amount`` is base + IGTF), but the invoice
        only owes its total: the IGTF is not a tax line of the invoice, it is
        settled apart (``pos.payment.method._create_payment_line``). Closing
        entries (no partner) are left as core builds them.
        """
        result = super()._prepare_account_move_line_data_for_payments(partner)
        for entry in result:
            metadata = entry["metadata"]
            payments = metadata.get("payments", self.env["pos.payment"]).filtered(
                "include_igtf"
            )
            igtf = self.currency_id[:1].round(sum(payments.mapped("igtf_amount")))
            metadata["igtf_amount"] = igtf
            metadata["foreign_igtf_amount"] = sum(payments.mapped("foreign_igtf_amount"))
            if igtf and partner:
                entry["account.move.line"]["amount_currency"] -= igtf
        return result
