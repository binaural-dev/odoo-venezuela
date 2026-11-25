from dateutil.relativedelta import relativedelta

from odoo.tests import Form, tagged
from odoo import fields, Command
from .retention_flow_helpers import RetentionFlowHelpers
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_municipal_reports")
class TestWizardMunicipalReports(RetentionFlowHelpers, RetentionTestCommon):

    def test_01_municipal_xlsx_wizard_creation(self):
        wizard = self.env["municipal.retention.xlsx.report"].create({
            "date_start": fields.Date.today(),
            "date_end": fields.Date.today(),
        })
        self.assertTrue(wizard)
        _logger.info("========= test_01 passed =========")

    def test_02_municipal_patent_wizard_creation(self):
        wizard = self.env["municipal.retention.patent.report"].create({
            "date_start": fields.Date.today(),
            "date_end": fields.Date.today(),
        })
        self.assertTrue(wizard)
        _logger.info("========= test_02 passed =========")

    def _patent_document(self, move_type, currency, amount, accounting_date=None):
        with Form(self.env["account.move"].with_context(
            default_move_type=move_type, default_journal_id=self.sale_journal.id,
        )) as form:
            form.partner_id = self.partner_pnr_75
            form.invoice_date = fields.Date.today()
            form.currency_id = currency
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = amount
        document = form.save()
        if accounting_date:
            document.date = accounting_date
        document.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(document.currency_id, currency)
        return document

    def test_03_patent_report_adds_foreign_documents_in_bolivares(self):
        """Gross sales and refunds of each CIU are in bolivares: a document in dollars counts at
        the rate of its own entry, not as if its dollar amount were bolivares (task 87658)."""
        self.company.account_fiscal_country_id = self.company.country_id
        self.sale_journal.currency_id = False
        activity = self._economic_activity()
        self.product_iva.ciu_ids = [Command.set(activity.ids)]
        self._patent_document("out_invoice", self.currency_vef, 10000.0)
        self._patent_document("out_invoice", self.currency_usd, 100.0)
        self._patent_document("out_refund", self.currency_usd, 20.0)

        today = fields.Date.today()
        wizard = self.env["municipal.retention.patent.report"].create({
            "date_start": today.replace(day=1),
            "date_end": today,
        })
        table = wizard._get_xlsx_municipality_retention_report()
        rows = table[table["CIU"] == activity.name]

        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(
            rows.iloc[0]["VENTAS BRUTAS (Factura + ND)"], 10000.0 + 100.0 * self.rate, places=2
        )
        self.assertAlmostEqual(
            rows.iloc[0]["DEVOLUC. VENTAS (NC)"], round(20.0 * self.rate, 2), places=2
        )

    def test_04_patent_report_takes_the_documents_of_its_accounting_month(self):
        """The month of the report is the accounting date of each document, as in the sale book: an
        invoice whose accounting date is in the previous month counts there and not in the month it
        was created in, whatever its invoice date (task 87658, defect B)."""
        self.company.account_fiscal_country_id = self.company.country_id
        self.sale_journal.currency_id = False
        activity = self._economic_activity()
        self.product_iva.ciu_ids = [Command.set(activity.ids)]
        today = fields.Date.today()
        previous_month = today.replace(day=1) - relativedelta(days=1)
        self._patent_document("out_invoice", self.currency_vef, 10000.0)
        late = self._patent_document(
            "out_invoice", self.currency_vef, 500.0, accounting_date=previous_month
        )
        self.assertEqual(late.date, previous_month)
        self.assertEqual(late.invoice_date_display, today)

        def gross_sales(date_start, date_end):
            wizard = self.env["municipal.retention.patent.report"].create({
                "date_start": date_start,
                "date_end": date_end,
            })
            table = wizard._get_xlsx_municipality_retention_report()
            rows = table[table["CIU"] == activity.name]
            return rows.iloc[0]["VENTAS BRUTAS (Factura + ND)"] if len(rows) else 0.0

        self.assertAlmostEqual(gross_sales(today.replace(day=1), today), 10000.0, places=2)
        self.assertAlmostEqual(
            gross_sales(previous_month.replace(day=1), previous_month), 500.0, places=2
        )
