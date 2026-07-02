import logging
from odoo.tests import tagged, Form
from odoo.exceptions import UserError, ValidationError
from odoo import Command, fields

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("islr_retention_partner", "-at_install", "post_install")
class TestISLRRetention(RetentionTestCommon):

    """ def setUp(self):
        super().setUp()
        self.tax_unit = self.env["tax.unit"].create({
            "name": "UT ISLR Test",
            "value": 100.0,
            "available_date": fields.Date.today(),
            "status": True,
        })
        self.islr_tariff = self.env["fees.retention"].create({
            "name": "ISLR 3% Test",
            "percentage": 3.0,
            "accumulated_rate": False,
            "tax_unit_ids": self.tax_unit.id,
            "status": True,
        })
        self.islr_concept_line = self.env["payment.concept.line"].create({
            "pay_from": 0.0,
            "type_person_id": self.env.ref(
                "l10n_ve_payment_extension.type_person_l10n_ve_payment_extension"
            ).id,
            "payment_concept_id": self.concept_one.id,
            "percentage_tax_base": 90.0,
            "tariff_id": self.islr_tariff.id,
            "code": "ISLR-TEST-90-3",
        }) """

    def test_islr_supplier_flow_complete(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertEqual(invoice.count_islr_retention, 1)
        self.assertTrue(invoice.islr_voucher_number,
                        "Supplier invoice must have ISLR voucher number")
        self.assertTrue(invoice.has_emited_islr_retention,
                        "Supplier must have emitted ISLR retention")
        ret = invoice.retention_islr_line_ids[0].retention_id
        self.assertEqual(ret.type_retention, "islr")
        self.assertEqual(ret.type, "in_invoice")
        self.assertEqual(ret.state, "emitted",
                         "Supplier ISLR retention must be emitted on creation")

    def test_islr_supplier_all_fields(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_islr_line_ids[0].retention_id
        line = invoice.retention_islr_line_ids[0]
        pay = ret.payment_ids[0]

        # ── account.retention ──
        self.assertEqual(ret.type_retention, "islr")
        self.assertEqual(ret.type, "in_invoice")
        self.assertEqual(ret.partner_id, invoice.partner_id)
        self.assertEqual(ret.state, "emitted")
        self.assertTrue(ret.number, "Supplier ISLR retention must have auto-generated number")
        self.assertTrue(ret.name, "Name must be set")
        self.assertEqual(ret.date_accounting, fields.Date.today())
        self.assertEqual(ret.date, fields.Date.today())
        self.assertEqual(ret.company_currency_id, self.currency_vef)
        self.assertEqual(ret.foreign_currency_id, self.currency_usd)
        self.assertTrue(ret.base_currency_is_vef)
        self.assertEqual(ret.total_invoice_amount, 1000.0)
        self.assertEqual(ret.total_iva_amount, 0.0,
                         "ISLR retention has no IVA component")
        self.assertEqual(ret.total_retention_amount, 27.0)
        # foreign amounts are not computed for ISLR retention lines in the current model
        self.assertEqual(ret.foreign_total_invoice_amount, 0.0)
        self.assertEqual(ret.foreign_total_iva_amount, 0.0)
        self.assertEqual(ret.foreign_total_retention_amount, 0.0)
        self.assertTrue(ret.payment_ids)
        self.assertTrue(ret.retention_line_ids)
        self.assertIn(invoice.id, ret.actual_invoice_ids.ids)

        # ── account.retention.line ──
        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.retention_id, ret)
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertEqual(line.iva_amount, 0.0,
                         "ISLR line has no IVA amount")
        self.assertEqual(line.invoice_total, 1000.0,
                         "ISLR-only invoice total equals base")
        self.assertEqual(line.retention_amount, 27.0)
        self.assertEqual(line.aliquot, 0.0,
                         "ISLR line has no aliquot (IVA tax rate)")
        self.assertEqual(line.related_percentage_tax_base, 90.0)
        self.assertEqual(line.related_percentage_fees, 3.0)
        self.assertEqual(line.related_amount_subtract_fees, 0.0)
        self.assertEqual(line.state, "emitted")
        self.assertEqual(line.name, "ISLR Retention")
        self.assertEqual(line.invoice_type, "in_invoice")
        self.assertTrue(line.payment_id)
        self.assertEqual(line.payment_concept_id, self.concept_one)
        # foreign amounts are not computed for ISLR lines in the current model
        self.assertEqual(line.foreign_invoice_amount, 0.0)
        self.assertEqual(line.foreign_iva_amount, 0.0)
        self.assertEqual(line.foreign_retention_amount, 0.0)
        self.assertEqual(line.company_currency_id, self.currency_vef)
        self.assertEqual(line.foreign_currency_id, self.currency_usd)
        self.assertTrue(line.date_accounting, fields.Date.today())

        # ── account.payment ──
        self.assertTrue(pay.is_retention)
        self.assertEqual(pay.payment_type_retention, "islr")
        self.assertEqual(pay.retention_id, ret)
        self.assertEqual(pay.state, "paid")
        self.assertAlmostEqual(pay.amount, 27.0, places=2)
        self.assertEqual(pay.partner_id, invoice.partner_id)
        self.assertEqual(pay.currency_id, self.currency_vef)
        self.assertEqual(pay.retention_ref, ret.number)
        # foreign amounts not computed for ISLR
        self.assertEqual(pay.retention_foreign_amount, 0.0)
        self.assertTrue(pay.retention_line_ids)

        # ── account.move (invoice) ──
        self.assertTrue(invoice.islr_voucher_number)
        self.assertTrue(invoice.is_isrl_retention_available)
        self.assertEqual(invoice.count_islr_retention, 1)
        self.assertTrue(invoice.has_emited_islr_retention)

    def test_islr_supplier_calculation(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        line = invoice.retention_islr_line_ids[0]
        ret = line.retention_id
        pay = ret.payment_ids[0]

        expected = 1000.0 * 0.90 * 0.03  # 27.0
        self.assertAlmostEqual(line.retention_amount, expected, places=2,
                               msg="retention_amount must be 1000 × 0.90 × 0.03 = 27.0")
        self.assertEqual(line.related_percentage_tax_base, 90.0)
        self.assertEqual(line.related_percentage_fees, 3.0)
        self.assertAlmostEqual(ret.total_retention_amount, expected, places=2)
        self.assertAlmostEqual(pay.amount, expected, places=2)
        self.assertEqual(pay.state, "paid")

    def test_islr_supplier_cancel_all_fields(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_islr_line_ids[0].retention_id
        line = invoice.retention_islr_line_ids[0]
        pay = ret.payment_ids[0]

        ret.action_cancel()
        line.invalidate_recordset()
        ret.invalidate_recordset()

        # retention
        self.assertEqual(ret.state, "cancel")
        self.assertFalse(ret.payment_ids)

        # line-domain hides cancelled lines
        self.assertFalse(invoice.retention_islr_line_ids)
        self.assertEqual(line.state, "cancel")
        self.assertFalse(line.payment_id, "Payment link must be cleared on line")

        # payment
        self.assertEqual(pay.state, "canceled")
        self.assertFalse(pay.retention_id)
        self.assertFalse(pay.is_retention)
        self.assertFalse(pay.payment_type_retention)
        self.assertFalse(pay.retention_ref)

        # invoice
        self.assertFalse(invoice.islr_voucher_number)
        self.assertEqual(invoice.count_islr_retention, 0)
        self.assertFalse(invoice.has_emited_islr_retention)

    def test_islr_no_type_person(self):
        partner_no_type = self.partner_ordinary
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=partner_no_type,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available,
                        "ISLR is available (product has concept), but partner has no type_person")
        invoice.generate_islr_retention = True
        with self.assertRaises(UserError) as cm:
            invoice.with_context(move_action_post_alert=True).action_post()
        self.assertIn("type of person", str(cm.exception).lower(),
                      "Must raise UserError about missing type person")

    def test_islr_no_journal(self):
        self.company.islr_supplier_retention_journal_id = False
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.generate_islr_retention = True
        with self.assertRaises(UserError) as cm:
            invoice.with_context(move_action_post_alert=True).action_post()
        self.assertIn("journal", str(cm.exception).lower(),
                      "Must raise UserError about missing ISLR journal")

    def test_islr_no_payment_concept(self):
        invoice = self._create_invoice_reten_iva(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self.assertFalse(invoice.is_isrl_retention_available,
                         "No ISLR available when product has no payment_concept")
        invoice.generate_islr_retention = True
        invoice._compute_retention_islr_avalability()
        self.assertFalse(invoice.generate_islr_retention,
                         "generate_islr_retention must be reset to False when ISLR not available")

    def test_islr_customer_flow_draft(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        self.assertEqual(invoice.count_islr_retention, 1)
        self.assertTrue(invoice.islr_voucher_number,
                        "Customer invoice gets ISLR voucher number even on draft retention")
        self.assertFalse(invoice.has_emited_islr_retention,
                         "Customer must not have emitted ISLR retention")
        ret = invoice.retention_islr_line_ids[0].retention_id
        self.assertEqual(ret.state, "draft",
                         "Customer ISLR retention must stay in draft")
        self.assertEqual(ret.type_retention, "islr")
        self.assertEqual(ret.type, "out_invoice")
        self.assertTrue(ret.number, "Customer ISLR retention gets auto-number in draft")
        # No payments in draft for ISLR customer (unlike IVA)
        self.assertFalse(ret.payment_ids,
                         "No payments exist for customer ISLR draft retention")

    def test_islr_customer_all_fields_draft(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_islr_line_ids[0].retention_id
        line = invoice.retention_islr_line_ids[0]

        # retention (draft)
        self.assertEqual(ret.type_retention, "islr")
        self.assertEqual(ret.type, "out_invoice")
        self.assertEqual(ret.partner_id, invoice.partner_id)
        self.assertEqual(ret.state, "draft",
                         "Customer ISLR retention must stay in draft")
        self.assertTrue(ret.number, "Customer ISLR retention gets auto-number in draft")
        self.assertFalse(ret.payment_ids,
                         "No payments for customer ISLR in draft")
        self.assertTrue(ret.retention_line_ids)

        # line (draft — ISLR computed fields are 0 for customer by design;
        # _get_islr_type_person_id returns company partner type, which doesn't match)
        self.assertEqual(line.move_id, invoice)
        self.assertEqual(line.retention_id, ret)
        self.assertEqual(line.invoice_amount, 1000.0,
                         "invoice_amount IS set from default_get")
        self.assertEqual(line.iva_amount, 0.0)
        self.assertEqual(line.invoice_total, 0.0,
                         "invoice_total stays 0 for customer (no concept match)")
        self.assertEqual(line.retention_amount, 0.0,
                         "retention_amount is 0 for customer draft (no computed concept)")
        self.assertEqual(line.aliquot, 0.0)
        self.assertEqual(line.related_percentage_tax_base, 0.0,
                         "related_* fields stay 0 for customer (no concept match)")
        self.assertEqual(line.related_percentage_fees, 0.0)
        self.assertEqual(line.related_amount_subtract_fees, 0.0)
        self.assertEqual(line.state, "draft")
        self.assertEqual(line.name, "ISLR Retention")
        self.assertEqual(line.invoice_type, "out_invoice")
        self.assertFalse(line.payment_id,
                         "No payment link in draft for ISLR customer")
        self.assertEqual(line.payment_concept_id, self.concept_one)

        # retention totals
        self.assertEqual(ret.total_invoice_amount, 1000.0)
        self.assertEqual(ret.total_iva_amount, 0.0)
        self.assertEqual(ret.total_retention_amount, 0.0,
                         "total_retention_amount is 0 for customer draft")
        self.assertEqual(ret.foreign_total_invoice_amount, 0.0)
        self.assertEqual(ret.foreign_total_iva_amount, 0.0)
        self.assertEqual(ret.foreign_total_retention_amount, 0.0)

        # invoice
        self.assertTrue(invoice.islr_voucher_number,
                        "Customer invoice gets ISLR voucher number even on draft retention")
        self.assertEqual(invoice.count_islr_retention, 1)
        self.assertFalse(invoice.has_emited_islr_retention)

    def test_islr_customer_post_and_cancel(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self.assertTrue(invoice.is_isrl_retention_available)
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_islr_line_ids[0].retention_id

        # Verify draft state — all amounts are 0 (customer ISLR not auto-computed)
        self.assertEqual(ret.state, "draft")
        self.assertTrue(ret.number, "Customer retention has number in draft")
        self.assertEqual(ret.total_retention_amount, 0.0,
                         "Customer ISLR has 0 amount in draft (no auto-concept match)")
        self.assertFalse(ret.payment_ids)

        # Posting a customer ISLR retention with 0 amount fails at reconciliation
        # (same as IVA customer — 0-amount payment has no reconcilable lines)
        with self.assertRaises(ValidationError) as cm:
            ret.action_post()
        self.assertIn("No registered lines found in the move to reconcile",
                      str(cm.exception))

        # State unchanged (still draft after failed post)
        self.assertEqual(ret.state, "draft")

        # ── Cancel draft retention ──
        pay = ret.payment_ids[0] if ret.payment_ids else None
        ret.action_cancel()
        ret.invalidate_recordset()

        self.assertEqual(ret.state, "cancel")
        self.assertFalse(ret.payment_ids)
        if pay:
            self.assertEqual(pay.state, "canceled")
            self.assertFalse(pay.retention_id)
            self.assertFalse(pay.is_retention)
        self.assertFalse(invoice.islr_voucher_number)
        self.assertEqual(invoice.count_islr_retention, 0)
        self.assertFalse(invoice.has_emited_islr_retention)
