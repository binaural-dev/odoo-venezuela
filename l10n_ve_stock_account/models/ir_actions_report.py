from odoo import models, _
from odoo.exceptions import ValidationError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)

        if (
            report.report_name
            == "l10n_ve_invoice.template_invoice_free_form_l10n_ve_invoice"
            and res_ids
        ):
            invoices = self.env["account.move"].browse(res_ids)
            if any(inv.move_type in ("in_invoice", "in_refund") for inv in invoices):
                raise ValidationError(
                    _("You cannot download a freeform from a vendor bill.")
                )

        return super()._render_qweb_pdf(report_ref, res_ids, data)
