from odoo import models, fields, api

class AccountInvoice(models.Model):
    _inherit = 'account.move'

    printed = fields.Boolean(default=False)