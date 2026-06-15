from odoo.tests import tagged
from odoo import fields
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_municipal_reports")
class TestWizardMunicipalReports(RetentionTestCommon):

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
