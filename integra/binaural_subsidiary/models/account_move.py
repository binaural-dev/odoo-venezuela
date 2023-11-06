import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"
    
    # subsidiary = fields.Char("Subsidiary", required=False)
    account_analytic_id = fields.Many2one("account.analytic.account", string="Analytic Account")
    
    
     # Relational
    # partner_id = fields.Many2one("res.partner", string="Partner", required=True)
    # property_id = fields.Many2one("estate.property", string="Property", required=True)
    
    
    # For stat button:
    
    

    # correlative = fields.Char("Control Number", copy=False, help="Sequence control number")
    # invoice_reception_date = fields.Date(
    #     "Reception Date", help="Indicates when the invoice was received by the client/company"
    # )
    # last_payment_date = fields.Date(
    #     compute="_compute_last_payment_date",
    #     store=True
    # )

        