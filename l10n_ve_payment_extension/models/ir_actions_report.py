from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        if (
            self._get_report(report_ref).report_name
            == "l10n_ve_payment_extension.retention_voucher_template"
        ):
            retention_ids = self.env["account.retention"].browse(res_ids)
            for retention in retention_ids:
                if retention.state == "draft":
                    raise ValidationError(
                        _("You cannot download a withholding slip in draft status. ")
                    )
            if retention_ids and all(
                retention.type_retention == "municipal" for retention in retention_ids
            ):
                self = self.with_context(municipal_voucher_portrait=True)
        return super(IrActionsReport, self)._render_qweb_pdf(report_ref, res_ids, data)

    def get_paperformat(self):
        """Municipal vouchers are printed in portrait; IVA/ISLR keep landscape."""
        if (
            self.env.context.get("municipal_voucher_portrait")
            and self.report_name == "l10n_ve_payment_extension.retention_voucher_template"
        ):
            return self.env.ref(
                "l10n_ve_payment_extension.paper_format_retention_municipal_voucher"
            )
        return super().get_paperformat()
