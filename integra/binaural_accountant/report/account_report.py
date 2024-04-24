from odoo import api, models

import logging
_logger = logging.getLogger(__name__)

class AccountReport(models.AbstractModel):
    _name = "report.binaural_accountant.account_report_call"

    def get_report_values(
        self,
        model_name,
        docids,
        data=None,
    ):
        docs = self.env[model_name].browse(docids)

        return {
            "doc_ids": docids,
            "doc_model": model_name,
            "docs": docs,
            "data": data,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        docids = data["docids"]

        return self.get_report_values("account.move.line", docids, data)
