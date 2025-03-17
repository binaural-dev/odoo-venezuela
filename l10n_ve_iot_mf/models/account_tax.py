from odoo import models, fields


class AccountTaxInherit(models.Model):
    _inherit = "account.tax"

    fiscal_code = fields.Integer(default=0)
