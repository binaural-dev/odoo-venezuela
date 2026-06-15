from odoo.tests import tagged
from odoo import fields
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "wizard_islr_report")
class TestWizardIslrReport(RetentionTestCommon):

    def test_01_wizard_islr_creation(self):
        wizard = self.env["wizard.retention.islr"].create({
            "report": "islr",
            "date_start": fields.Date.today(),
            "date_end": fields.Date.today(),
        })
        self.assertTrue(wizard)
        _logger.info("========= test_01 passed =========")

    def test_02_wizard_islr_download_format(self):
        wizard = self.env["wizard.retention.islr"].create({
            "report": "islr",
            "date_start": fields.Date.today(),
            "date_end": fields.Date.today(),
        })
        ext = wizard.download_format()
        self.assertEqual(ext, ".xlsm")
        _logger.info("========= test_02 passed =========")

    def test_03_wizard_retention_iva_creation(self):
        wizard = self.env["wizard.retention.iva"].create({
            "date_start": fields.Date.today(),
            "date_end": fields.Date.today(),
        })
        self.assertTrue(wizard)
        _logger.info("========= test_03 passed =========")
