from odoo import models, api, _
from odoo.exceptions import ValidationError


class BinauralPaymentExtensionRetentionIvaVoucher(models.AbstractModel):
    _name = "report.l10n_ve_payment_extension.retention_voucher_template"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs_retentions = self.env["account.retention"].browse(docids)
        if any(retention.type_retention == "municipal" for retention in docs_retentions):
            raise ValidationError(
                _("Municipal retentions do not have PDF voucher. Please print the xslx")
            )

        return {
            "docids": docids,
            "doc_model": "account.retention",
            "foreign_currency_is_vef": self.get_foreign_currency_is_vef(),
            "get_digits": self.get_digits(),
            "docs": docs_retentions,
        }

    def get_digits(self):
        decimal_places = self.env.ref("base.VEF").decimal_places
        return decimal_places

    def get_foreign_currency_is_vef(self):
        return self.env.company.currency_foreign_id == self.env.ref("base.VEF")
