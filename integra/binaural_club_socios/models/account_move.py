from odoo import models, api, exceptions, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    action_number = fields.Char(related='partner_id.action_number.number', readonly=True)
    
    fee_period = fields.Date(string='Periodo de la cuota')
    
    pay_soon = fields.Boolean(string='Pronto Pago')

    def check_solvent_partner(self):
            for record in self:
                invoices = record.partner_id.invoice_ids.filtered(lambda x: x.payment_state in ['not_paid', 'partial'])
                if len(invoices) > 0:
                    record.partner_id.write({'is_solvent': False})
                else:
                    record.partner_id.write({'is_solvent': True})

    def write(self, vals):
        res = super().write(vals)
        self.check_solvent_partner()
        return res

    @api.model
    def create(self, vals):
        res = super().create(vals)
        res.partner_id.write({'is_solvent': False})
        return res
