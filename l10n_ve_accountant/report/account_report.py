from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class AccountReport(models.AbstractModel):
    _name = "report.l10n_ve_accountant.account_report_call"

    @api.model
    def _get_report_values(self, docids, data=None):
        if not docids:
            raise ValidationError(_("docids empty"))

        current_invoice = self.env["account.move"].browse(docids[0])
        
        data = current_invoice.get_account_move_report_data()

        return {
            "doc_ids": data["doc_ids"],
            "doc_model": "account.move.line",
            "docs": data["docs"],
            "data": data,
        }

class AccountReportRelated(models.AbstractModel):
    _name = "report.l10n_ve_accountant.account_related_report_call"
    _inherit = ["report.l10n_ve_accountant.account_report_call"]
