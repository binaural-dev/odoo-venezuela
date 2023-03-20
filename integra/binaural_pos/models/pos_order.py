from odoo import models, fields, api, _


class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one("res.currency", related="company_id.currency_foreign_id")
    foreign_amount_total = fields.Float(string='Total', digits=0, readonly=True, required=True)

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["foreign_amount_total"] = ui_order["foreign_amount_total"]
        return res
