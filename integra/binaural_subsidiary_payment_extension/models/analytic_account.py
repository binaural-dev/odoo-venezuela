from odoo import api, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    tax_authorities_logo = fields.Image(max_width=128, max_height=128)
    tax_authorities_name = fields.Char()
    economic_activity_number = fields.Char()
    municipality_id = fields.Many2one("res.country.municipality", required=True)
