from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = "account.payment"
    
    proof_of_payment = fields.Many2many(
        'ir.attachment',
        'proof_of_payment_rel',
        'proof_of_payment_id',
        'attachment_id'
    )
    retention_receipt = fields.Many2many(
        'ir.attachment',
        'retention_receipt_rel',
        'retention_receipt_id',
        'attachment_id'
    )
    taxpayer_type = fields.Selection(
        related='partner_id.taxpayer_type'
    )
    
    def write(self, vals):
        if 'ref' in vals:
            memo = self.search([('ref', '=', vals['ref'])])
            if any(memo):
                raise ValidationError(
                    'El memo del pago debe ser unico')
        return super().write(vals)
    
    
    @api.model
    def create(self, vals):
        if 'ref' in vals and vals['ref']:
            memo = self.search([('ref', '=', vals['ref'])])
            if any(memo):
                raise ValidationError(
                    'El memo del pago debe ser unico')
        return super().create(vals)