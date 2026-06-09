from odoo.tests import tagged
from odoo import fields
from odoo.tests.common import TransactionCase
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "report_arcv")
class TestReportArcv(TransactionCase):

    def test_01_arcv_report_creation(self):
        partner = self.env["res.partner"].search([], limit=1)
        self.assertTrue(partner)
        wizard = self.env["arcv.report"].create({
            "date_start": fields.Date.today(),
            "date_end": fields.Date.today(),
            "partner_id": partner.id,
        })
        self.assertTrue(wizard)
        _logger.info("========= test_01 passed =========")
