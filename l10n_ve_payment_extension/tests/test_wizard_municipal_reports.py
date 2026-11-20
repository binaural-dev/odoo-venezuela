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

    def _patent_document(self, move_type, currency, amount):
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
