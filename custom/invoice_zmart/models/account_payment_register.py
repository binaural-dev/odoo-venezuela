from odoo import models, fields, api

class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"
    
    proof_of_payment = fields.Binary()
    retention_receipt = fields.Binary()
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
        payment.proof_of_payment = self.proof_of_payment
        payment.retention_receipt = self.retention_receipt
        return res