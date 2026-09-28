from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged, Form

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
        inv.invoice_date_display = invoice_date
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.with_context(move_action_post_alert=True).action_post()
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

    def test_03_retention_period_uses_accounting_date_not_emission_date(self):
        today = fields.Date.today()
        old_invoice_date = today - timedelta(days=40)

        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": today - timedelta(days=10),
            "date_to": today + timedelta(days=1),
        })

        inv_in_range = self._make_sale_invoice(100, old_invoice_date)
        self._make_sale_iva_retention_with_dates(
            inv_in_range, date=old_invoice_date, date_accounting=today,
        )

        inv_out_of_range = self._make_sale_invoice(100, old_invoice_date)
        self._make_sale_iva_retention_with_dates(
            inv_out_of_range, date=today, date_accounting=old_invoice_date,
        )

        data = wizard.parse_sale_book_data()
        ret_lines = [line for line in data if line.get("move_type") == "RET"]

        self.assertEqual(len(ret_lines), 1)
        _logger.info("========= test_03 passed =========")

    def _setup_igtf_fixtures(self):
        """Fixtures mínimas de l10n_ve_igtf: cuenta IGTF y diario en USD
        marcado como `is_igtf`, necesarios para que una factura acumule
        `alter_bi_igtf` al pagarse parcialmente por ese diario."""
        acc_igtf_cli = self.get_or_create_account(
            "236IGTF", "liability_current", "IGTF Clientes",
        )
        self.company.write({
            "igtf_percentage": 3.0,
            "customer_account_igtf_id": acc_igtf_cli.id,
        })

        account_bank_usd = self.get_or_create_account(
            "1002", "asset_cash", "Cuenta de Banco USD",
        )
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        pm_line_in_usd = self.env["account.payment.method.line"].create({
            "name": "Manual Inbound USD",
            "payment_method_id": manual_in.id,
            "payment_type": "inbound",
            "payment_account_id": account_bank_usd.id,
        })
        bank_journal_usd = self.Journal.create({
            "name": "Banco USD IGTF",
            "code": "BNKUSD",
            "type": "bank",
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "is_igtf": True,
            "default_account_id": account_bank_usd.id,
            "inbound_payment_method_line_ids": [(6, 0, pm_line_in_usd.ids)],
        })
        pm_line_in_usd.journal_id = bank_journal_usd.id
        return bank_journal_usd

    def _make_sale_invoice_usd(self, amount, invoice_date):
        with Form(self.env["account.move"].with_context(
            default_move_type="out_invoice", default_journal_id=self.sale_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = invoice_date
            inv_form.currency_id = self.currency_usd

        inv = inv_form.save()
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = amount
        inv = inv_form_edit.save()

        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.with_context(move_action_post_alert=True).action_post()
        return inv

    def test_04_retention_row_zeroes_all_numeric_fields_including_igtf(self):
        today = fields.Date.today()
        bank_journal_usd = self._setup_igtf_fixtures()

        inv = self._make_sale_invoice_usd(2681.20, today)

        with Form.from_action(self.env, inv.action_register_payment()) as pay_form:
            pay_form.journal_id = bank_journal_usd
            pay_form.payment_date = today
            pay_form.save()
            pay_form.amount = 2000.00
            pay_form.save()
        pay_form.record.action_create_payments()

        retention = self._make_sale_iva_retention(inv, today)

        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": today - timedelta(days=10),
            "date_to": today + timedelta(days=10),
        })
        data = wizard.parse_sale_book_data()

        fac_lines = [line for line in data if line.get("move_type") == "FAC"]
        ret_lines = [line for line in data if line.get("move_type") == "RET"]
        self.assertEqual(len(fac_lines), 1)
        self.assertEqual(len(ret_lines), 1)

        fac_line = fac_lines[0]
        ret_line = ret_lines[0]

        self.assertNotEqual(fac_line.get("igtf"), 0)
        self.assertEqual(ret_line.get("igtf"), 0)

        numeric_fields = {
            field["field"]
            for group in wizard._get_sale_book_field_groups()
            for field in group.get("fields", [])
            if field.get("format") == "number"
        }
        for field_name in numeric_fields:
            if field_name == "iva_withheld" or field_name not in ret_line:
                continue
            self.assertEqual(
                ret_line[field_name], 0,
                f"Campo numérico '{field_name}' de la fila RET debería ser 0, "
                f"encontrado: {ret_line[field_name]}",
            )
        _logger.info("========= test_04 passed =========")
