from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)

class AccountPaymentRegisterClub(models.TransientModel):
    _inherit = "account.payment.register"

    def _create_payments(self):
        res = super()._create_payments()
        for payment in res:
            if payment.reconciled_invoice_ids:
                payment.reconciled_invoice_ids.check_solvent_partner()
        return res