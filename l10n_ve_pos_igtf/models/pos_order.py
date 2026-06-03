from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero, float_round, float_repr

class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float(string="IGTF Amount")
    bi_igtf = fields.Float(string="BI IGTF")

    def _process_order(self, order, existing_order):
        try:
            order["igtf_amount"] = float(order.get("igtf_amount", 0.0) or 0.0)
        except (TypeError, ValueError):
            order["igtf_amount"] = 0.0

        try:
            order["bi_igtf"] = float(order.get("bi_igtf", 0.0) or 0.0)
        except (TypeError, ValueError):
            order["bi_igtf"] = 0.0

        return super()._process_order(order, existing_order)

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order, ui_paymentline)
        res["include_igtf"] = ui_paymentline.get("include_igtf", False)
        res["igtf_amount"] = ui_paymentline.get("igtf_amount", 0)
        res["foreign_igtf_amount"] = ui_paymentline.get("foreign_igtf_amount", 0)
        return res

    def _create_invoice(self, move_vals):
        res = super()._create_invoice(move_vals)
        res.write({"bi_igtf": abs(self.bi_igtf)})
        return res
    
    @api.model
    def get_order_from_back(self, id):
        order = self.env['pos.order'].search([
            ('id', '=', id),
        ], limit=1)

        if not order:
            return {
                'amount_total': 0.0,
                'igtf_amount': 0.0,
                'bi_igtf': 0.0,
            }

        return {
            'amount_total': order.amount_total,
            'amount_paid': order.amount_paid,
            'igtf_amount': order.igtf_amount,
            'bi_igtf': order.bi_igtf,
        }
    
    def action_pos_order_paid(self):
        self.ensure_one()
        # Keep the standard behavior for non-refund orders.
        if not self.is_refund:
            try:
                return super().action_pos_order_paid()
            except UserError:
                _logger.warning(
                    "[IGTF][DEBUG][BE] non-refund unpaid order=%s total=%s amount_paid=%s diff=%s currency_rounding=%s",
                    self.name,
                    float_repr(self.amount_total, self.currency_id.decimal_places),
                    float_repr(self.amount_paid, self.currency_id.decimal_places),
                    float_repr(self.amount_total - self.amount_paid, self.currency_id.decimal_places),
                    self.currency_id.rounding,
                )
                raise

        # For refunds, validate against a compensated paid amount when IGTF is already
        # embedded in payment lines, to avoid rejecting valid IGTF-inclusive refunds.
        if not self.config_id.cash_rounding \
           or self.config_id.only_round_cash_method \
           and not any(p.payment_method_id.is_cash_count for p in self.payment_ids):
            total = self.amount_total
        else:
            total = float_round(
                self.amount_total,
                precision_rounding=self.config_id.rounding_method.rounding,
                rounding_method=self.config_id.rounding_method.rounding_method,
            )

        payment_igtf_amount = sum(
            abs(payment.igtf_amount)
            for payment in self.payment_ids
            if payment.include_igtf and payment.igtf_amount
        )
        order_igtf_amount = abs(self.igtf_amount or 0.0)
        refund_igtf_for_validation = order_igtf_amount or payment_igtf_amount

        adjusted_paid = self.amount_paid
        if refund_igtf_for_validation:
            adjusted_paid = (
                self.amount_paid + refund_igtf_for_validation
                if self.amount_paid < 0
                else self.amount_paid - refund_igtf_for_validation
            )

        rounded_total = float_round(total, precision_rounding=self.currency_id.rounding)
        rounded_paid = float_round(adjusted_paid, precision_rounding=self.currency_id.rounding)
        rounded_diff = rounded_total - rounded_paid
        is_paid = float_is_zero(rounded_diff, precision_rounding=self.currency_id.rounding)

        _logger.warning(
            "[IGTF][DEBUG][BE] refund order=%s total=%s amount_paid=%s adjusted_paid=%s order_igtf=%s payment_igtf=%s applied_igtf=%s rounded_total=%s rounded_paid=%s rounded_diff=%s is_paid=%s",
            self.name,
            float_repr(total, self.currency_id.decimal_places),
            float_repr(self.amount_paid, self.currency_id.decimal_places),
            float_repr(adjusted_paid, self.currency_id.decimal_places),
            float_repr(order_igtf_amount, self.currency_id.decimal_places),
            float_repr(payment_igtf_amount, self.currency_id.decimal_places),
            float_repr(refund_igtf_for_validation, self.currency_id.decimal_places),
            float_repr(rounded_total, self.currency_id.decimal_places),
            float_repr(rounded_paid, self.currency_id.decimal_places),
            float_repr(rounded_diff, self.currency_id.decimal_places),
            is_paid,
        )

        if not is_paid and not self.config_id.cash_rounding:
            raise UserError(_("Order %s is not fully paid.", self.name))
        elif not is_paid and self.config_id.cash_rounding:
            currency = self.currency_id
            if self.config_id.rounding_method.rounding_method == "HALF-UP":
                maxDiff = currency.round(self.config_id.rounding_method.rounding / 2)
            else:
                maxDiff = currency.round(self.config_id.rounding_method.rounding)

            diff = currency.round(total - adjusted_paid)
            if not abs(diff) <= maxDiff:
                raise UserError(_("Order %s is not fully paid.", self.name))

        self.write({'state': 'paid'})
        return True
