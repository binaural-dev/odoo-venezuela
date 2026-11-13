from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_round


class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float()
    bi_igtf = fields.Float()

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["igtf_amount"] = ui_order["igtf_amount"]
        return res

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order, ui_paymentline)
        res["include_igtf"] = ui_paymentline["include_igtf"]
        res["igtf_amount"] = ui_paymentline.get("igtf_amount", 0)
        res["foreign_igtf_amount"] = ui_paymentline.get("foreign_igtf_amount", 0)

        return res

    def _get_total_with_igtf(self):
        self.ensure_one()
        # amount_total ya incluye el IGTF: order_model.js sobreescribe
        # get_total_with_tax() para sumarlo del lado del frontend antes de
        # exportar la orden. Sumarlo de nuevo aquí lo contaba dos veces y
        # dejaba el pedido en borrador (isPaid=False) por la diferencia
        # exacta del IGTF.
        return self.currency_id.round(self.amount_total)

    def action_pos_order_paid(self):
        self.ensure_one()

        if self.currency_id.is_zero(self.igtf_amount):
            return super().action_pos_order_paid()

        total_with_igtf = self._get_total_with_igtf()

        if not self.config_id.cash_rounding \
           or self.config_id.only_round_cash_method \
           and not any(p.payment_method_id.is_cash_count for p in self.payment_ids):
            total = total_with_igtf
        else:
            total = float_round(
                total_with_igtf,
                precision_rounding=self.config_id.rounding_method.rounding,
                rounding_method=self.config_id.rounding_method.rounding_method,
            )

        isPaid = float_is_zero(
            total - self.amount_paid,
            precision_rounding=self.currency_id.rounding,
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

    def _create_invoice(self, move_vals):
        res = super()._create_invoice(move_vals)
        res.write({"bi_igtf": abs(self.bi_igtf)})
        return res

    def _apply_invoice_payments(self, is_reverse=False):
        """Same as the standard Odoo implementation, but resolving
        ``receivable_account`` through ``pos.payment._get_pos_receivable_account``
        instead of reading ``property_account_receivable_id`` directly.

        Standard Odoo looks up the receivable account straight from the
        partner's property to find the invoice/payment lines to reconcile.
        When the partner has none (e.g. a contact created on the fly from
        the POS), that lookup returns an empty account, so the
        ``if receivable_account.reconcile:`` guard below is skipped and the
        invoice is never reconciled against its payment, even though
        ``_create_payment_moves`` already credited the payment to the
        invoice's own receivable account via the same fallback.
        """
        accounting_partner = self.env["res.partner"]._find_accounting_partner(
            self.partner_id
        )
        receivable_account = self.env["pos.payment"]._get_pos_receivable_account(
            accounting_partner, self
        )
        payment_moves = self.payment_ids.sudo().with_company(
            self.company_id
        )._create_payment_moves(is_reverse)
        if receivable_account.reconcile:
            invoice_receivables = self.account_move.line_ids.filtered(
                lambda line: line.account_id == receivable_account
                and not line.reconciled
            )
            if invoice_receivables:
                credit_line_ids = payment_moves._context.get("credit_line_ids", None)
                payment_receivables = payment_moves.mapped("line_ids").filtered(
                    lambda line: (
                        (credit_line_ids and line.id in credit_line_ids)
                        or (
                            not credit_line_ids
                            and line.account_id == receivable_account
                            and line.partner_id
                        )
                    )
                )
                (invoice_receivables | payment_receivables).sudo().with_company(
                    self.company_id
                ).reconcile()
        return payment_moves
