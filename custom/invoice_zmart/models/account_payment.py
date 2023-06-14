from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountPaymentZmart(models.Model):
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