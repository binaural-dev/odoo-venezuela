from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "sale_book_retention_lines")
class TestSaleBookRetentionLines(RetentionTestCommon):

    def _make_sale_invoice(self, amount, invoice_date):
        inv = self._create_invoice_reten_iva(
            amount, self.partner_pnr_75,
            "out_invoice", self.sale_journal,
        )
        inv.invoice_date = invoice_date
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        return inv

    def _make_sale_iva_retention(self, invoice, retention_date):
        return self._make_sale_iva_retention_with_dates(invoice, retention_date, retention_date)

    def _make_sale_iva_retention_with_dates(self, invoice, date, date_accounting):
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": date,
            "date_accounting": date_accounting,
            "state": "emitted",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "IVA Retention Line",
                "invoice_total": invoice.amount_total,
                "invoice_amount": invoice.amount_untaxed,
                "retention_amount": invoice.amount_untaxed * 0.75,
                "foreign_currency_rate": 1.0,
                "foreign_invoice_amount": invoice.amount_untaxed,
                "foreign_retention_amount": invoice.amount_untaxed * 0.75,
            })],
        })

    def test_01_retention_creates_independent_row_with_expected_fields(self):
        today = fields.Date.today()
        invoice_date = today - timedelta(days=5)
        retention_date = today
        inv = self._make_sale_invoice(200, invoice_date)
        retention = self._make_sale_iva_retention(inv, retention_date)

        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": today - timedelta(days=10),
            "date_to": today + timedelta(days=10),
        })
        data = wizard.parse_sale_book_data()
        _logger.info("=== DEBUG data: %s", data)
        _logger.info("=== DEBUG inv state=%s date=%s invoice_date=%s", inv.state, inv.date, inv.invoice_date)
        _logger.info("=== DEBUG retention state=%s date=%s date_accounting=%s", retention.state, retention.date, retention.date_accounting)

        fac_lines = [line for line in data if line.get("move_type") == "FAC"]
        ret_lines = [line for line in data if line.get("move_type") == "RET"]
        self.assertEqual(len(data), 2)
        self.assertEqual(len(fac_lines), 1)
        self.assertEqual(len(ret_lines), 1)

        ret_line = ret_lines[0]
        self.assertEqual(ret_line["transaction_type"], "04-REG")
        self.assertEqual(ret_line["document_date"], wizard._format_date(retention.date))
        self.assertEqual(ret_line["total_sales"], 0)
        self.assertEqual(ret_line["total_sales_iva"], 0)
        self.assertEqual(ret_line["total_sales_not_iva"], 0)
        self.assertEqual(ret_line["amount_reduced_aliquot"], 0)
        self.assertEqual(ret_line["amount_general_aliquot"], 0)
        self.assertEqual(ret_line["amount_extend_aliquot"], 0)
        self.assertEqual(ret_line["tax_base_reduced_aliquot"], 0)
        self.assertEqual(ret_line["tax_base_general_aliquot"], 0)
        self.assertEqual(ret_line["tax_base_extend_aliquot"], 0)
        self.assertEqual(ret_line["retention_date"], wizard._format_date(retention.date))
        self.assertEqual(ret_line["retention_number"], retention.number or "--")
        self.assertNotEqual(ret_line["iva_withheld"], 0)

        fac_line = fac_lines[0]
        self.assertEqual(fac_line["retention_date"], "--")
        self.assertEqual(fac_line["retention_number"], "--")
        self.assertEqual(fac_line["iva_withheld"], 0)
        _logger.info("========= test_01 passed =========")

    def test_02_parse_sale_book_data_sorts_rows_by_document_date(self):
        today = fields.Date.today()
        inv_1 = self._make_sale_invoice(100, today - timedelta(days=6))
        inv_2 = self._make_sale_invoice(100, today - timedelta(days=3))
        retention = self._make_sale_iva_retention(inv_2, today)

        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": today - timedelta(days=10),
            "date_to": today + timedelta(days=1),
        })
        data = wizard.parse_sale_book_data()

        expected_dates = [
            wizard._format_date(today - timedelta(days=6)),
            wizard._format_date(today - timedelta(days=3)),
            wizard._format_date(today),
        ]
        actual_dates = [line["document_date"] for line in data]
        self.assertEqual(actual_dates, expected_dates)
        _logger.info("========= test_02 passed =========")

    def test_03_retention_period_uses_emission_date_not_accounting_date(self):
        today = fields.Date.today()
        old_invoice_date = today - timedelta(days=40)

        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": today - timedelta(days=10),
            "date_to": today + timedelta(days=1),
        })

        inv_in_range = self._make_sale_invoice(100, old_invoice_date)
        self._make_sale_iva_retention_with_dates(
            inv_in_range, date=today, date_accounting=old_invoice_date,
        )

        inv_out_of_range = self._make_sale_invoice(100, old_invoice_date)
        self._make_sale_iva_retention_with_dates(
            inv_out_of_range, date=old_invoice_date, date_accounting=today,
        )

        data = wizard.parse_sale_book_data()
        ret_lines = [line for line in data if line.get("move_type") == "RET"]

        self.assertEqual(len(ret_lines), 1)
        _logger.info("========= test_03 passed =========")
