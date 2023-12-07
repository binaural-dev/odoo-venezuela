from odoo import fields, models


class AccountAnalitycAccount(models.Model):
    _inherit = "account.analytic.account"

    is_subsidiary = fields.Boolean(default=False)
