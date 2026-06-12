from odoo.tests import tagged
from odoo import fields
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_accounting_reports")
class TestWizardAccountingReports(RetentionTestCommon):

    def test_01_accounting_report_wizard_creation(self):
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "purchase",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        self.assertTrue(wizard)
        self.assertEqual(wizard.report, "purchase")
        _logger.info("========= test_01 passed =========")

    def test_02_accounting_report_wizard_sale(self):
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        self.assertTrue(wizard)
        _logger.info("========= test_02 passed =========")
