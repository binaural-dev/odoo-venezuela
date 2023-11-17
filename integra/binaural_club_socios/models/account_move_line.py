from odoo import models, api, exceptions, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    action_number = fields.Char(related='partner_id.action_number.number', string="Action Number")
    