from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    sh_pos_order_analytic_account = fields.Many2one(string="Subsidiary")

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["sh_pos_order_analytic_account"] = ui_order["sh_pos_order_analytic_account"]
        return res

    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        res["sh_pos_order_analytic_account"] = order.sh_pos_order_analytic_account
        return res
