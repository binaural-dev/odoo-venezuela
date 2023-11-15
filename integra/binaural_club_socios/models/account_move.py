from odoo import models, api, exceptions, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    action_number = fields.Char(related='partner_id.action_number.number', readonly=True)
