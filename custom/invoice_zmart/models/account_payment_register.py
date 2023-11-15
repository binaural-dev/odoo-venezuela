from odoo import models, fields, api

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    proof_of_payment = fields.Many2many(
        'ir.attachment',
        'proof_of_payment_rel_1',
        'proof_of_payment_id',
        'attachment_id'
    )
    retention_receipt = fields.Many2many(
        'ir.attachment',
        'retention_receipt_rel_1',
        'retention_receipt_id',
        'attachment_id'
    )
    taxpayer_type = fields.Selection(
        related='partner_id.taxpayer_type'
    )
    
    def action_create_payments(self):
        res = super().action_create_payments()
        partner_id = self.partner_id.id
        payment = self.env['account.payment'].search(
            [
            ('partner_id', '=', partner_id)
            ], 
            order="create_date desc", 
            limit=1)
        payment.write({
            'proof_of_payment': [(6, 0, self.proof_of_payment.ids)],
            'retention_receipt': [(6, 0, self.retention_receipt.ids)]
        })
        return res