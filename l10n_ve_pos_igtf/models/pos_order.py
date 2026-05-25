from odoo import models, fields, api, _


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
