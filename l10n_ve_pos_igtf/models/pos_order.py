from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero, float_round, float_repr, float_compare, formatLang

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
        res = super().action_pos_order_paid()
        if self.is_refund: #TODO: borro la validacion para ver que pasa
            if not self.config_id.cash_rounding \
            or self.config_id.only_round_cash_method \
            and not any(p.payment_method_id.is_cash_count for p in self.payment_ids):
                total = self.amount_total
            else:
                total = float_round(self.amount_total, precision_rounding=self.config_id.rounding_method.rounding, rounding_method=self.config_id.rounding_method.rounding_method)

            isPaid = True

            if not isPaid and not self.config_id.cash_rounding:
                raise UserError(_("Order %s is not fully paid.", self.name))
            elif not isPaid and self.config_id.cash_rounding:
                currency = self.currency_id
                if self.config_id.rounding_method.rounding_method == "HALF-UP":
                    maxDiff = currency.round(self.config_id.rounding_method.rounding / 2)
                else:
                    maxDiff = currency.round(self.config_id.rounding_method.rounding)

                diff = currency.round(self.amount_total - self.amount_paid)
                if not abs(diff) <= maxDiff:
                    raise UserError(_("Order %s is not fully paid.", self.name))

            self.write({'state': 'paid'})
            return True
        return res
