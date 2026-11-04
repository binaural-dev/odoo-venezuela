from odoo import models, api
from odoo.tools.misc import formatLang


MONEY_COLUMNS = ("Base Imponible", "Impuesto Municipal Retenido", "Impuesto Retenido")
PERCENT_COLUMN = "Alícuota %"
RETAINED_COLUMN = "Impuesto Retenido"


class PaymentExtensionRetentionIvaVoucher(models.AbstractModel):
    _name = "report.l10n_ve_payment_extension.retention_voucher_template"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs_retentions = self.env["account.retention"].browse(docids)
        municipal_data = {
            retention.id: self._get_municipal_retention_data(retention)
            for retention in docs_retentions
            if retention.type_retention == "municipal"
        }
        return {
            "docids": docids,
            "doc_model": "account.retention",
            "foreign_currency_is_vef": self.get_foreign_currency_is_vef(),
            "get_digits": self.get_digits(),
            "docs": docs_retentions,
            "municipal_data": municipal_data,
        }

    def get_digits(self):
        decimal_places = self.env.ref("base.VEF").decimal_places
        return decimal_places

    def get_foreign_currency_is_vef(self):
        return self.env.company.foreign_currency_id == self.env.ref("base.VEF")

    def _get_municipal_retention_data(self, retention):
        """Prepare header and table of a municipal retention voucher.

        Reuses the same sources as the XLSX report so both outputs keep the
        same logic: `_get_tax_authorities_record` (hook overridden by
        subsidiaries in integra-addons) and `get_xlsx_municipal_retention`
        (9 columns, currency selection, amounts without sign changes).
        """
        xlsx_model = self.env["municipal.retention.xlsx"]
        tax_auth = xlsx_model._get_tax_authorities_record(
            self.env.company, retention.id
        )
        table = xlsx_model.get_xlsx_municipal_retention(retention.id)
        columns = list(table.columns.values)
        rows = table.values.tolist()
        vef = self.env.ref("base.VEF")
        money_columns = {
            index for index, name in enumerate(columns) if name in MONEY_COLUMNS
        }
        percent_columns = {
            index for index, name in enumerate(columns) if name == PERCENT_COLUMN
        }
        display_rows = []
        for row in rows:
            display = []
            for index, value in enumerate(row):
                if index in money_columns:
                    value = formatLang(self.env, value, currency_obj=vef)
                elif index in percent_columns:
                    value = "%s %%" % formatLang(self.env, value * 100, digits=2)
                display.append(value)
            display_rows.append(display)
        retained_index = columns.index(RETAINED_COLUMN) if rows else None
        total = sum(row[retained_index] for row in rows)
        return {
            "tax_auth": tax_auth,
            "columns": columns,
            "rows": rows,
            "display_rows": display_rows,
            "total": total,
            "total_display": formatLang(self.env, total, currency_obj=vef),
        }
