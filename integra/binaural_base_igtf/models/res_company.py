from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    account_igtf_id = fields.Many2one("account.account")
    igtf_percentage = fields.Float(string="IGTF Percentage", default=3.00)
