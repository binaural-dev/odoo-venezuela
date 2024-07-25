from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountAnalitycAccount(models.Model):
    _inherit = "account.analytic.account"

    dairy_fiscal = fields.Many2one("account.journal")
    dairy_no_fiscal = fields.Many2one("account.journal")