from odoo import fields, models, _
from collections import defaultdict


class ArcvReport(models.TransientModel):
    _name = "arcv.report"
    _description = "Generate ARCV Report"

    partner_id = fields.Many2one("res.partner", required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)

    def print_arcv(self):
        retentions_by_month_and_percentage_fees = (
            self._get_islr_retention_lines_grouped_by_year_month_and_percentage_fees()
        )
        data = self._construct_report_data(retentions_by_month_and_percentage_fees)
        return self.env.ref("l10n_ve_payment_extension.action_report_arcv").report_action(
            None, data=data
        )

    def _get_islr_retention_lines_grouped_by_year_month_and_percentage_fees(self):
        """
        Returns a dictionary with the following structure:
        {
            (year, month, percentage_fees): [account.retention.line, ...],
            ...
        }

        Containing the retention lines that match the following criteria:
            - Type of retention: ISLR.
            - Type of invoice: Supplier invoice.
            - Partner: The partner selected in the wizard.
            - State: Emitted.
            - Date accounting: Between the start and end date selected in the wizard.

        This is useful to group the retention lines by year, month and percentage fees, which is
        the way they are displayed in the report.

        Returns
        -------
        dict
            Dictionary with the structure described above.
        """
        islr_retention_lines = self.env["account.retention.line"].search(
            [
                ("retention_id.type_retention", "=", "islr"),
                ("retention_id.type", "=", "in_invoice"),
                ("retention_id.partner_id", "=", self.partner_id.id),
                ("state", "=", "emitted"),
                ("retention_id.date_accounting", ">=", self.date_start),
                ("retention_id.date_accounting", "<=", self.date_end),
            ],
            order="date_accounting",
        )

        # We use a defaultdict to avoid having to check if the key exists before adding a new
        # element to the list.
        def get_empty_retention_line():
            return self.env["account.retention.line"]

        retentions_by_month_and_percentage_fees = defaultdict(get_empty_retention_line)

        for line in islr_retention_lines:
            retentions_by_month_and_percentage_fees[
                (
                    line.date_accounting.year,
                    line.date_accounting.month,
                    line.related_percentage_fees,
                )
            ] += line
        return retentions_by_month_and_percentage_fees

    def _construct_report_data(self, retentions_by_month_and_percentage_fees):
        """
        Returns a dictionary with the data that will be used to generate the report.

        This is the structure of the dictionary:
        {
            "period": {
                "start": "01/01/2020",
                "end": "31/01/2020",
            },
            "partner": {
                "name": "Partner Name",
                "street": "Partner Street",
                "street2": "Partner Street 2",
                "phone": "Partner Phone",
                "vat": "Partner VAT",
            },
            "retentions": [
                {
                    "period": "01/2020",
                    "percentage_fees": 0.75,
                    "invoice_paid_amount_not_related_with_retentions": 900.0,
                    "total_invoice_amount": 10000.0,
                    "total_retention_amount": 100.0,
                },
                ...
            ],
        }

        Parameters
        ----------
        retentions_by_month_and_percentage_fees : dict
            Dictionary with the corresponding retention lines grouped by year, month and percentage
            fees.

        Returns
        -------
        dict
            Dictionary with the structure described above.
        """
        retentions_data = []
        for (
            year,
            month,
            percentage_fees,
        ), lines in retentions_by_month_and_percentage_fees.items():
            retentions_data.append(
                {
                    "currency": lines[0].company_currency_id.id,
                    "period": f"{month}/{year}",
                    "percentage_fees": percentage_fees,
                    "invoice_paid_amount_not_related_with_retentions": (
                        lines.get_invoice_paid_amount_not_related_with_retentions()
                    ),
                    "total_invoice_amount": sum(line.invoice_amount for line in lines),
                    "total_retention_amount": sum(line.retention_amount for line in lines),                    
                    "total_foreign_invoice_amount": sum(line.foreign_invoice_amount for line in lines),
                    "total_foreign_retention_amount": sum(line.foreign_retention_amount for line in lines),
                }
            )
        data = {
            "period": {
                "start": self.date_start.strftime("%d/%m/%Y"),
                "end": self.date_end.strftime("%d/%m/%Y"),
            },
            "partner": {
                "name": self.partner_id.name,
                "street": self.partner_id.street,
                "street2": self.partner_id.street2,
                "phone": self.partner_id.phone,
                "vat": f"{self.partner_id.prefix_vat}-{self.partner_id.vat}",
            },
            "retentions": retentions_data,
        }
        return data
