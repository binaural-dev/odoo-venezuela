from odoo import api, fields, models, _

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_foreign_id = fields.Many2one(
        "res.currency",
        string="Currency Foreign",
        help="Currency Foreign for the company"
    )