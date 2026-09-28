import base64
import logging

from odoo import fields
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)

# 1x1 transparent PNG, used as a stand-in for a configured signature image.
TEST_PNG_B64 = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAA"
    b"AAYAAjCB0C8AAAAASUVORK5CYII="
)


@tagged("post_install", "-at_install", "municipal_retention_xlsx")
class TestMunicipalRetentionXlsxReport(RetentionTestCommon):
    """Regression tests for the /web/get_xlsx_municipal_retention download.

    Before the fix, `municipal.retention.xlsx.xlsx_file()` called
    `odoo.tools.image_process`, a name that no longer exists on the
    `odoo.tools` package in this Odoo version (it now only lives under
    `odoo.tools.image`). Whenever a company had an active signature
    configured, that call raised an AttributeError and the XLSX download
    failed with an internal server error.
    """

    def _create_municipal_retention(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        retention = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "date_emision": fields.Date.today(),
            "retention_line_ids": [(0, 0, {
                "move_id": inv.id,
                "aliquot": 5.0,
                "invoice_amount": 200.0,
                "retention_amount": 10.0,
            })],
        })
        return retention

    def test_xlsx_file_with_active_signature_does_not_raise(self):
        self.env["signature.config"].create({
            "email": "firma@test.com",
            "signature": TEST_PNG_B64,
            "active": True,
            "company_id": self.company.id,
        })

        retention = self._create_municipal_retention()
        report_model = self.env["municipal.retention.xlsx"]
        table = report_model.get_xlsx_municipal_retention(retention.id)
        filecontent = report_model.xlsx_file(table, "Test Municipal Retention", retention.id)

        self.assertTrue(filecontent)
        self.assertEqual(filecontent[:2], b"PK")  # valid XLSX/ZIP file signature
        _logger.info("========= test_xlsx_file_with_active_signature_does_not_raise passed =========")

    def test_xlsx_file_without_signature_does_not_raise(self):
        self.env["signature.config"].search([]).write({"active": False})

        retention = self._create_municipal_retention()
        report_model = self.env["municipal.retention.xlsx"]
        table = report_model.get_xlsx_municipal_retention(retention.id)
        filecontent = report_model.xlsx_file(table, "Test Municipal Retention", retention.id)

        self.assertTrue(filecontent)
        self.assertEqual(filecontent[:2], b"PK")
        _logger.info("========= test_xlsx_file_without_signature_does_not_raise passed =========")
