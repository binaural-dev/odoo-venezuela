from odoo import models, api


class BinauralPaymentExtensionRetentionIvaVoucher(models.AbstractModel):
    _name = "report.binaural_payment_extension.template_retention_iva_voucher"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs_retentions = self.env["account.retention"].browse(docids)

        return {
            "docids": docids,
            "doc_model": "account.retention",
            "get_foreign_currency_id": self.get_foreign_currency_id(),
            "get_digits": self.get_digits(),
            "docs": docs_retentions
        }

    def get_digits(self):
        currency_foreign_id = self.env.company.currency_foreign_id.id

        decimal_places = self.env["res.currency"].search([
            ("id", '=', currency_foreign_id)
        ]).decimal_places

        return decimal_places

    def get_foreign_currency_id(self):
        currency_foreign_id = self.env.company.currency_foreign_id.id
        return currency_foreign_id
