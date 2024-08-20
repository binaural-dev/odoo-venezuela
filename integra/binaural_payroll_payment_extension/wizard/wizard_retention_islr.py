from odoo import models, fields, api, _
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)


class RetentionIslrReport(models.TransientModel):
    _inherit = "wizard.retention.islr"

    # payslip
    def _get_payslip_line_domain(self, current_company_id=False):
        domain = [
            ("slip_id.date_to", ">=", self.date_start), 
            ("slip_id.date_to", "<=", self.date_end),
            ("salary_rule_id.code", "=", "PM-ISLR"),
            ("slip_id.state", "in", ["done", "paid"])
        ]

        if current_company_id:
            domain += [("company_id", "=", current_company_id)]

        return domain

    def _get_payslip_line_ids(self, current_company_id=False):
        domain = self._get_payslip_line_domain()

        payslip_line_ids  = self.env["hr.payslip.line"].search(domain)

        return payslip_line_ids

    @api.model    
    def _get_from_payslip_retention_islr_excel_row(self, row_idx, slip_line_id, is_vef_currency):

        new_row = self._get_retention_islr_excel_model_row()

        slip_id = slip_line_id.slip_id

        new_row["ID Sec"] = row_idx

        new_row["RIF Retenido"] = f"{slip_id.employee_id.prefix_vat}{slip_id.employee_id.vat}"

        pi = str(slip_id.date_to)

        fpi = datetime.strptime(pi, "%Y-%m-%d")

        new_row["Número factura"] = 0

        new_row["Control Número"] = "NA"

        new_row["Fecha Operación"] = fpi.strftime("%d/%m/%Y")

        new_row["Código Concepto"] = 1

        new_row["Monto Operación"] = (
            (round(slip_line_id.foreign_total, 2) if is_vef_currency else slip_line_id.total) * -1
        )

        new_row["Porcentaje de retención"] = slip_id.employee_id.porc_ari

        return new_row

    def _get_from_payslip_retention_islr_excel_rows(self, table_rows, row_idx, current_company=False):
        is_vef_currency = self.env.ref("base.VEF").id == self.env.company.currency_foreign_id.id

        payslip_line_ids = self._get_payslip_line_ids(current_company)

        for payslip_line_id in payslip_line_ids:
            row_idx += 1

            new_row = self._get_from_payslip_retention_islr_excel_row(row_idx, payslip_line_id, is_vef_currency)

            table_rows.append(new_row)

        return table_rows, row_idx



    def _get_retention_islr_excel_rows(self, table_rows, row_idx, current_company=False):
        table_rows, table_rows_count = super()._get_retention_islr_excel_rows(table_rows, row_idx, current_company)

        table_rows, table_rows_count = self._get_from_payslip_retention_islr_excel_rows(table_rows, table_rows_count, current_company)

        return table_rows, table_rows_count