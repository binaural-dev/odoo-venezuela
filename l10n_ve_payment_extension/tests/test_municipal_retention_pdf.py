import logging

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)

REPORT_REF = "l10n_ve_payment_extension.retention_voucher_template"


@tagged("post_install", "-at_install", "municipal_retention_pdf")
class TestMunicipalRetentionPdf(RetentionTestCommon):
    """PDF voucher of municipal retentions (ticket #15877).

    It must mirror the logic and restrictions of the XLSX report.
    """

    def _create_municipal_retention(self, **extra_vals):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        vals = {
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
        }
        vals.update(extra_vals)
        return self.env["account.retention"].create(vals)

    def _create_iva_retention(self):
        inv = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [(0, 0, {
                "move_id": inv.id,
                "invoice_amount": 200.0,
                "retention_amount": 10.0,
            })],
        })

    def _render(self, retentions):
        content, _fmt = self.env["ir.actions.report"]._render_qweb_pdf(
            REPORT_REF, res_ids=retentions.ids
        )
        if isinstance(content, bytes):
            content = content.decode()
        return content

    def test_01_municipal_pdf_renders(self):
        retention = self._create_municipal_retention()
        retention.state = "emitted"
        html = self._render(retention)
        self.assertIn("ACTIVIDADES ECONÓMICAS", html)
        self.assertNotIn("COMPROBANTE DE RETENCIÓN DE ISLR", html)
        _logger.info("========= test_01 passed =========")

    def test_02_mixed_batch_iva_and_municipal(self):
        municipal = self._create_municipal_retention()
        iva = self._create_iva_retention()
        (municipal | iva).write({"state": "emitted"})
        html = self._render(iva | municipal)
        self.assertIn("ACTIVIDADES ECONÓMICAS", html)
        self.assertIn("COMPROBANTE DE RETENCIÓN DEL IMPUESTO AL VALOR AGREGADO", html)
        _logger.info("========= test_02 passed =========")

    def test_03_header_from_company(self):
        self.company.write({
            "tax_authorities_name": "alcaldia de prueba",
            "economic_activity_number": "LIC-12345",
        })
        retention = self._create_municipal_retention()
        retention.state = "emitted"
        html = self._render(retention)
        self.assertIn("ALCALDIA DE PRUEBA", html)
        self.assertIn("LIC-12345", html)
        _logger.info("========= test_03 passed =========")

    def test_04_hide_issue_date(self):
        retention = self._create_municipal_retention()
        retention.state = "emitted"
        self.company.hide_issue_date_of_municipal_withholding_receipt = False
        html = self._render(retention)
        self.assertIn("FECHA DE EMISIÓN O TRANSACCIÓN", html)
        self.assertIn("FECHA DE ENTREGA", html)
        self.company.hide_issue_date_of_municipal_withholding_receipt = True
        html = self._render(retention)
        self.assertIn("FECHA DE EMISIÓN O TRANSACCIÓN", html)
        self.assertNotIn("FECHA DE ENTREGA", html)
        _logger.info("========= test_04 passed =========")

    def test_05_empty_date_emision_does_not_fail(self):
        retention = self._create_municipal_retention()
        retention.write({"state": "emitted", "date_emision": False})
        self.company.hide_issue_date_of_municipal_withholding_receipt = False
        html = self._render(retention)
        self.assertIn("FECHA DE ENTREGA", html)
        self.assertFalse(retention.date_emision)
        _logger.info("========= test_05 passed =========")

    def test_06_draft_municipal_raises(self):
        retention = self._create_municipal_retention()
        self.assertEqual(retention.state, "draft")
        with self.assertRaises(ValidationError):
            self._render(retention)
        _logger.info("========= test_06 passed =========")

    def test_07_rows_match_xlsx(self):
        retention = self._create_municipal_retention()
        retention.state = "emitted"
        table = self.env["municipal.retention.xlsx"].get_xlsx_municipal_retention(
            retention.id
        )
        data = self.env[
            "report.l10n_ve_payment_extension.retention_voucher_template"
        ]._get_municipal_retention_data(retention)
        self.assertEqual(data["columns"], list(table.columns.values))
        self.assertEqual(len(data["columns"]), 9)
        self.assertEqual(data["rows"], table.values.tolist())
        self.assertAlmostEqual(
            data["total"], sum(row[8] for row in table.values.tolist())
        )
        self.assertEqual(data["total"], 10.0)
        self.assertEqual(data["display_rows"][0][5], "5.00 %")
        _logger.info("========= test_07 passed =========")
