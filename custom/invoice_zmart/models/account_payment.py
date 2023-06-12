from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountPaymentIgtf(models.Model):
    _inherit = "account.payment"
    
    proof_of_payment = fields.Binary()
    retention_receipt = fields.Binary()
    taxpayer_type = fields.Selection(
        related='partner_id.taxpayer_type'
    )