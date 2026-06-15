from odoo.tests import tagged
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "payment_retention")
class TestPaymentRetention(RetentionTestCommon):

    def _prepare_invoice(self, invoice):
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})

    def _create_retention_with_payment(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        return retention

    def test_01_compute_rate_skips_retention(self):
        retention = self._create_retention_with_payment()
        for payment in retention.payment_ids:
            payment._compute_rate()
        _logger.info("========= test_01_compute_rate_skips_retention passed =========")

    def test_02_synchronize_to_moves_municipal(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice(invoice)
        invoice.action_post()
        branch = self.env["economic.branch"].create({
            "name": "TEST BRANCH",
        })
        self.env["economic.activity"].create({
            "name": "Act", "aliquot": 5.0,
            "municipality_id": self.env["res.country.municipality"].search([], limit=1).id,
            "branch_id": branch.id,
            "description": "T", "minimum_monthly": 0, "minimum_annual": 0,
        })
        self.company.write({"municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id})
        retention = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "Muni Line",
                "invoice_total": 200.0, "invoice_amount": 200.0,
                "retention_amount": 10.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 10.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        payment = retention.payment_ids[0]
        if hasattr(payment, "_synchronize_to_moves"):
            payment._synchronize_to_moves(payment.move_id)
        _logger.info("========= test_02_synchronize_to_moves_municipal passed =========")

    def test_03_unlink_blocked_for_retention(self):
        retention = self._create_retention_with_payment()
        for payment in retention.payment_ids:
            with self.assertRaises(UserError):
                payment.unlink()
        _logger.info("========= test_03_unlink_blocked_for_retention passed =========")

    def test_04_action_draft_blocked(self):
        retention = self._create_retention_with_payment()
        for payment in retention.payment_ids:
            with self.assertRaises(UserError):
                payment.action_draft()
        _logger.info("========= test_04_action_draft_blocked passed =========")

    def test_05_action_cancel_blocked(self):
        retention = self._create_retention_with_payment()
        for payment in retention.payment_ids:
            with self.assertRaises(UserError):
                payment.action_cancel()
        _logger.info("========= test_05_action_cancel_blocked passed =========")

    def test_06_validate_islr_supplier_no_journal(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        self.company.write({"islr_supplier_retention_journal_id": False})
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        with self.assertRaises(UserError):
            retention.action_post()
        _logger.info("========= test_06 passed =========")

    def test_07_unlink_emitted_blocked(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        with self.assertRaises(ValidationError):
            retention.unlink()
        _logger.info("========= test_07 passed =========")

    def test_08_unlink_draft_ok(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0,
            })],
        })
        retention.unlink()
        _logger.info("========= test_08 passed =========")

    def test_09_action_cancel_no_payments(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        self.company.write({"municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id})
        retention = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "Muni Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        _logger.info("========= test_09 passed =========")

    def test_10_action_cancel_twice_skips(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        self.company.write({"municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id})
        retention = self.env["account.retention"].create({
            "type_retention": "municipal", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "Muni Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        retention.action_cancel()
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        _logger.info("========= test_10 passed =========")

    def test_11_action_draft_blocked_for_posted(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        with self.assertRaises(UserError):
            retention.action_draft()
        _logger.info("========= test_11 passed =========")

    def test_12_create_third_party_retention_non_posted_raises(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        with self.assertRaises(UserError):
            self.env["account.retention"].create({
                "type_retention": "iva", "type": "in_invoice",
                "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
                "date": fields.Date.today(), "date_accounting": fields.Date.today(),
                "is_third_party_retention": True,
                "retention_line_ids": [Command.create({
                    "move_id": invoice.id, "name": "IVA Line",
                    "invoice_total": 232.0, "invoice_amount": 200.0,
                    "retention_amount": 32.0,
                })],
            })
        _logger.info("========= test_12 passed =========")

    def test_13_validate_islr_no_concepts(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        with self.assertRaises(UserError):
            invoice.validate_islr()
        _logger.info("========= test_13 passed =========")

    def test_14_action_create_islr_single_retention(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        result = invoice.action_create_islr_from_invoice()
        self.assertIn("res_model", result)
        self.assertEqual(result["res_model"], "account.retention")
        _logger.info("========= test_14 passed =========")

    def test_15_validate_islr_draft_state_raises(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        with self.assertRaises(UserError):
            invoice.validate_islr()
        _logger.info("========= test_15 passed =========")

    def test_16_get_payment_concepts_from_invoice(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        concepts = invoice._get_payment_concepts_from_invoice()
        self.assertGreater(len(concepts), 0)
        _logger.info("========= test_16 passed =========")

    def test_17_view_third_party_iva_retentions(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        action = invoice.action_view_third_party_iva_retentions()
        self.assertIn("type", action)
        self.assertEqual(action["type"], "ir.actions.act_window")
        _logger.info("========= test_17 passed =========")

    def test_18_view_third_party_islr_retentions(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        action = invoice.action_view_third_party_islr_retentions()
        self.assertIn("type", action)
        self.assertEqual(action["type"], "ir.actions.act_window")
        _logger.info("========= test_18 passed =========")

    def test_19_check_retention_amount_exceeds(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "out_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        retention_line = self.env["account.retention.line"].create({
            "name": "Test", "move_id": invoice.id,
            "retention_id": retention.id,
            "invoice_total": 232.0, "invoice_amount": 200.0,
            "retention_amount": 99999.0,
            "foreign_invoice_amount": 200.0,
            "foreign_retention_amount": 99999.0,
        })
        with self.assertRaises(ValidationError):
            retention_line.check_retention_amount()
        _logger.info("========= test_19 passed =========")

    def test_20_constraint_amounts_in_zero_non_draft(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        # Now set retention_amount to 0 on a posted line — triggers constraint
        with self.assertRaises(ValidationError):
            retention.retention_line_ids.write({"retention_amount": 0.0})
        _logger.info("========= test_20 passed =========")

    def test_21_get_islr_type_person_id_out_invoice(self):
        self.company.partner_id.write({
            "type_person_id": self.env.ref(
                "l10n_ve_payment_extension.type_person_l10n_ve_payment_extension"
            ).id,
        })
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "out_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "name": "ISLR Test", "move_id": invoice.id,
            "retention_id": retention.id,
            "invoice_total": 200.0, "invoice_amount": 200.0,
            "retention_amount": 6.0,
            "foreign_invoice_amount": 200.0,
            "foreign_retention_amount": 6.0,
        })
        type_person = line._get_islr_type_person_id()
        self.assertTrue(type_person)
        _logger.info("========= test_21 passed =========")

    def test_22_get_islr_type_person_id_supplier(self):
        invoice = self._create_invoice_islr(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "name": "ISLR Test", "move_id": invoice.id,
            "retention_id": retention.id,
            "invoice_total": 200.0, "invoice_amount": 200.0,
            "retention_amount": 6.0,
            "foreign_invoice_amount": 200.0,
            "foreign_retention_amount": 6.0,
        })
        type_person = line._get_islr_type_person_id()
        self.assertTrue(type_person)
        _logger.info("========= test_22 passed =========")

    def test_23_load_iva_retention_lines_no_taxes_warning(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        invoice.invoice_line_ids.write({"tax_ids": [Command.clear()]})
        wizard = self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create({
            "amount": invoice.amount_total,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        })
        result = wizard._load_iva_retention_lines(invoice)
        self.assertIn("warning", result)
        self.assertFalse(result["value"]["is_retention"])
        _logger.info("========= test_23 passed =========")

    def test_24_load_iva_retention_lines_existing_emitted_warning(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "out_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        wizard = self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create({
            "amount": invoice.amount_total,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        })
        result = wizard._load_iva_retention_lines(invoice)
        self.assertIn("warning", result)
        self.assertFalse(result["value"]["is_retention"])
        _logger.info("========= test_24 passed =========")

    def test_25_onchange_retention_disabled(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create({
            "amount": invoice.amount_total,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        })
        wizard.is_retention = False
        result = wizard._onchange_retention()
        self.assertIn("value", result)
        self.assertTrue(result["value"]["edit_retention_fields"])
        _logger.info("========= test_25 passed =========")

    def test_26_onchange_retention_line_ids_empty(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create({
            "amount": 50.0,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        })
        wizard.write({"retention_line_ids": [Command.clear()]})
        result = wizard._onchange_retention_line_ids()
        self.assertIsNone(result)
        _logger.info("========= test_26 passed =========")

    def test_27_compute_available_journal_ids_excludes_supplier(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self.env["account.payment.register"].with_context(
            active_ids=invoice.ids, active_model="account.move",
        ).create({
            "amount": invoice.amount_total,
            "payment_date": fields.Date.today(),
            "journal_id": self.bank_journal_sub.id,
        })
        wizard._compute_available_journal_ids()
        self.assertNotIn(self.bank_journal_sup_ret, wizard.available_journal_ids)
        _logger.info("========= test_27 passed =========")

    def test_28_accounting_report_retention_iva_values(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        invoice.iva_voucher_number = retention.number
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "purchase",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        wizard.currency_system = True
        ret_vals = wizard.get_retention_iva_values(invoice.id)
        self.assertIn("iva_retained", ret_vals)
        _logger.info("========= test_28 passed =========")

    def test_29_accounting_report_retention_iva_draft_move(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        invoice.iva_voucher_number = retention.number
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "purchase",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        ret_vals = wizard.get_retention_iva_values(invoice.id)
        self.assertEqual(ret_vals["iva_retained"], 0)
        _logger.info("========= test_29 passed =========")

    def test_30_sum_retention_total_skip_cancel(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "name": "Cancel Line", "move_id": invoice.id,
            "invoice_total": 100.0, "invoice_amount": 100.0,
            "retention_amount": 12.0, "foreign_invoice_amount": 100.0,
            "foreign_retention_amount": 12.0,
        })
        invoice.button_cancel()
        total = wizard._sum_retention_total(line)
        self.assertEqual(total, 0.0)
        _logger.info("========= test_30 passed =========")

    def test_31_sum_retention_total_non_vef(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
            "currency_system": False,
        })
        total = wizard._sum_retention_total(retention.retention_line_ids)
        self.assertGreaterEqual(total, 0.0)
        _logger.info("========= test_31 passed =========")

    def test_32_parse_sale_book_data(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "out_invoice", self.sale_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        data = wizard.parse_sale_book_data()
        self.assertIsInstance(data, list)
        _logger.info("========= test_32 passed =========")

    def test_33_parse_purchase_book_data(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "purchase",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        data = wizard.parse_purchase_book_data()
        self.assertIsInstance(data, list)
        _logger.info("========= test_33 passed =========")

    def test_34_determinate_resume_retention_books(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "sale",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        result = wizard._determinate_resume_retention_books(invoice)
        self.assertIsInstance(result, list)
        _logger.info("========= test_34 passed =========")

    def test_35_search_moves_with_retentions(self):
        invoice = self._create_invoice_reten_iva(
            200, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": invoice.id, "name": "IVA Line",
                "invoice_total": 232.0, "invoice_amount": 200.0,
                "retention_amount": 32.0, "foreign_invoice_amount": 200.0,
                "foreign_retention_amount": 32.0, "foreign_currency_rate": 1.0,
            })],
        })
        retention.number = "01234567891234"
        retention.action_post()
        wizard = self.env["wizard.accounting.reports"].create({
            "report": "purchase",
            "date_from": fields.Date.today(),
            "date_to": fields.Date.today(),
        })
        moves = wizard.search_moves()
        self.assertTrue(moves)
        _logger.info("========= test_35 passed =========")
