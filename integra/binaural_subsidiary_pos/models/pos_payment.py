from odoo import fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    sh_analytic_account = fields.Many2one(string="Subsidiary")
