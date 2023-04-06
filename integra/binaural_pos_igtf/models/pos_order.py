from odoo import models, fields, api, _


class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float()
    bi_igtf = fields.Float()

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["igtf_amount"] = ui_order["igtf_amount"]
        res["bi_igtf"] = ui_order["bi_igtf"]
        return res

    def _create_invoice(self, move_vals):
        res = super()._create_invoice(move_vals)
        res.write({"bi_igtf": self.bi_igtf})
        return res
