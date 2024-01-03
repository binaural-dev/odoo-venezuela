from odoo import fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"


    sh_pos_order_analytic_account = fields.Many2one(string="Subsidiary")
