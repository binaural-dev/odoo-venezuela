from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    sh_pos_order_analytic_account = fields.Many2one(string="Subsidiary")
