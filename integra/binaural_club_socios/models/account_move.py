from odoo import models, api, exceptions, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    action_number = fields.Char(string='Action Number', readonly=True)
