from odoo import models, api, exceptions, fields

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    action_number = fields.Char(string="Action Number", compute="_get_action", store=True)

    @api.depends('partner_id')
    def _get_action(self):
        for payment in self:
            if payment.partner_id and payment.partner_id.action_number:
                payment.action_number = payment.partner_id.action_number.number