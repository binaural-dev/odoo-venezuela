from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_lifecycle")
class TestRetentionLifecycle(RetentionTestCommon):

    def _prepare_invoice_for_retention(self, invoice):
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})

    def _create_iva_retention(self, invoice):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "retention_line_ids": [
                Command.create({
                    "move_id": invoice.id,
                    "name": "IVA Retention Line",
                    "invoice_total": invoice.amount_total,
                    "invoice_amount": invoice.amount_untaxed,
                    "retention_amount": float_round(invoice.amount_untaxed * 0.16, precision_rounding=0.01),
                    "foreign_currency_rate": 1.0,
                    "foreign_invoice_amount": invoice.amount_untaxed,
                    "foreign_retention_amount": float_round(invoice.amount_untaxed * 0.16, precision_rounding=0.01),
                })
            ],
        })

    def _create_islr_retention(self, invoice):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "retention_line_ids": [
                Command.create({
                    "move_id": invoice.id,
                    "name": "ISLR Retention Line",
                    "invoice_total": invoice.amount_total,
                    "invoice_amount": invoice.amount_untaxed,
                    "retention_amount": float_round(invoice.amount_untaxed * 0.03, precision_rounding=0.01),
                    "foreign_invoice_amount": invoice.amount_untaxed,
                    "foreign_retention_amount": float_round(invoice.amount_untaxed * 0.03, precision_rounding=0.01),
                    "payment_concept_id": self.concept_one.id,
                })
            ],
        })

    def _create_municipal_retention(self, invoice):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "retention_line_ids": [
                Command.create({
                    "move_id": invoice.id,
                    "name": "Municipal Retention Line",
                    "invoice_total": invoice.amount_total,
                    "invoice_amount": invoice.amount_untaxed,
                    "retention_amount": float_round(invoice.amount_untaxed * 0.05, precision_rounding=0.01),
                    "foreign_invoice_amount": invoice.amount_untaxed,
                    "foreign_retention_amount": float_round(invoice.amount_untaxed * 0.05, precision_rounding=0.01),
                })
            ],
        })

    def test_01_get_sequences(self):
        seq_iva = self.env["account.retention"].get_sequence_iva_retention()
        self.assertTrue(seq_iva)
        self.assertEqual(seq_iva.code, "retention.iva.control.number")

        seq_islr = self.env["account.retention"].get_sequence_islr_retention()
        self.assertTrue(seq_islr)
        self.assertEqual(seq_islr.code, "retention.islr.control.number")

        seq_municipal = self.env["account.retention"].get_sequence_municipal_retention()
        self.assertTrue(seq_municipal)
        self.assertEqual(seq_municipal.code, "retention.municipal.control.number")

        _logger.info("========= test_01_get_sequences passed =========")

    def test_02_sequence_creation_when_missing(self):
        self.env["ir.sequence"].search([
            ("code", "=", "retention.iva.control.number"),
        ]).unlink()
        seq_iva = self.env["account.retention"].get_sequence_iva_retention()
        self.assertTrue(seq_iva)
        self.assertEqual(seq_iva.padding, 8)

        self.env["ir.sequence"].search([
            ("code", "=", "retention.islr.control.number"),
        ]).unlink()
        seq_islr = self.env["account.retention"].get_sequence_islr_retention()
        self.assertTrue(seq_islr)
        self.assertEqual(seq_islr.padding, 5)

        _logger.info("========= test_02_sequence_creation_when_missing passed =========")

    def test_03_iva_retention_lifecycle(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()

        retention = self._create_iva_retention(invoice)
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.type_retention, "iva")

        retention.number = "01234567891234"
        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.number)
        self.assertTrue(retention.retention_line_ids)
        self.assertTrue(retention.payment_ids)

        payment = retention.payment_ids[0]
        self.assertTrue(payment.is_retention)
        self.assertEqual(payment.retention_id.id, retention.id)

        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")

        retention.action_draft()
        self.assertEqual(retention.state, "draft")

        _logger.info("========= test_03_iva_retention_lifecycle passed =========")

    def test_04_iva_retention_number_validation(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        retention = self._create_iva_retention(invoice)
        retention.number = "0123456789"
        with self.assertRaises(ValidationError) as e:
            retention.action_post()
        self.assertIn("14 numeric digits", str(e.exception))

        _logger.info("========= test_04_iva_retention_number_validation passed =========")

    def test_05_customer_retention_number_required(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        retention = self._create_iva_retention(invoice)
        retention.type = "out_invoice"
        retention.number = False
        with self.assertRaises(UserError) as e:
            retention.action_post()
        self.assertIn("Insert a number", str(e.exception))

        _logger.info("========= test_05_customer_retention_number_required passed =========")

    def test_06_unlink_emitted_retention(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        retention = self._create_iva_retention(invoice)
        retention.number = "01234567891234"
        retention.action_post()
        with self.assertRaises(ValidationError):
            retention.unlink()

        _logger.info("========= test_06_unlink_emitted_retention passed =========")

    def test_07_compute_display_name(self):
        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        retention.write({"number": False, "name": "/"})
        retention.invalidate_recordset()
        self.assertEqual(retention.display_name, "/")

        retention.write({"name": "RET-TEST-001"})
        retention.invalidate_recordset()
        self.assertTrue(retention.display_name in ("RET-TEST-001", "/"))

        retention.write({"number": "01234567891234"})
        retention.invalidate_recordset()
        self.assertEqual(retention.display_name, "01234567891234")

        _logger.info("========= test_07_compute_display_name passed =========")

    def test_08_islr_retention_lifecycle(self):
        invoice = self._create_invoice_islr(
            amount=500, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        retention = self._create_islr_retention(invoice)
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.type_retention, "islr")

        retention.number = "01234567891234"
        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(retention.payment_ids)
        invoice.invalidate_recordset()
        self.assertTrue(invoice.islr_voucher_number)

        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")

        _logger.info("========= test_08_islr_retention_lifecycle passed =========")

    def test_09_municipal_retention_lifecycle(self):
        self.company.write({
            "municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
        })
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        retention = self._create_municipal_retention(invoice)
        self.assertEqual(retention.state, "draft")
        retention.number = "01234567891234"
        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")

        _logger.info("========= test_09_municipal_retention_lifecycle passed =========")

    def test_10_set_voucher_number_in_invoice(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        self.env["account.retention"].set_voucher_number_in_invoice(invoice, self.env["account.retention"].new({
            "type_retention": "iva", "number": "IVA-TEST-001",
        }))
        self.assertEqual(invoice.iva_voucher_number, "IVA-TEST-001")

        self.env["account.retention"].set_voucher_number_in_invoice(invoice, self.env["account.retention"].new({
            "type_retention": "islr", "number": "ISLR-TEST-001",
        }))
        self.assertEqual(invoice.islr_voucher_number, "ISLR-TEST-001")

        self.env["account.retention"].set_voucher_number_in_invoice(invoice, self.env["account.retention"].new({
            "type_retention": "municipal", "number": "MUN-TEST-001",
        }))
        self.assertEqual(invoice.municipal_voucher_number, "MUN-TEST-001")

        _logger.info("========= test_10_set_voucher_number_in_invoice passed =========")

    def test_11_clear_retention_number(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        retention = self._create_iva_retention(invoice)
        retention.number = "01234567891234"
        retention.action_post()
        self.assertTrue(invoice.iva_voucher_number)
        retention.action_cancel()
        retention.clear_retention_number()
        invoice.invalidate_recordset()
        self.assertFalse(invoice.iva_voucher_number)

        _logger.info("========= test_11_clear_retention_number passed =========")

    def test_12_compute_retention_lines_data(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        lines_data = self.env["account.retention"].compute_retention_lines_data(invoice)
        self.assertTrue(lines_data)
        self.assertIn("invoice_amount", lines_data[0])

        _logger.info("========= test_12_compute_retention_lines_data passed =========")
