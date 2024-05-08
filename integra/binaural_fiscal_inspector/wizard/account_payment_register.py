from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.depends("payment_type", "company_id", "can_edit_wizard")
    def _compute_available_journal_ids(self):
        res = super()._compute_available_journal_ids()
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            for wizard in self:
                wizard.available_journal_ids = wizard.available_journal_ids.filtered_domain(
                    [("fiscal","=",True)]
                )
        return res
