import logging

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "customer_iva_retention_no_sequence")
class TestCustomerIvaRetentionNoSequence(RetentionTestCommon):
    """The IVA retention generated when posting a customer invoice must not
    take a number from retention.iva.control.number (the correlative of the
    vouchers we issue to suppliers): the customer, as withholding agent,
    issues the number and it is typed in before posting the retention."""

    FORM = "l10n_ve_payment_extension.view_retention_iva_form_l10n_ve_payment_extension"

    def _sequence_next(self):
        return self.env["account.retention"].get_sequence_retention("iva").number_next_actual

    def _customer_invoice(self):
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.generate_iva_retention = True
        return invoice

    def _draft_retention(self, invoice):
        return invoice.retention_iva_line_ids.retention_id.filtered(
            lambda r: r.state != "cancel"
        )

    def test_01_customer_draft_has_no_number_and_keeps_sequence(self):
        before = self._sequence_next()
        invoice = self._customer_invoice()
        invoice.action_post()
        retention = self._draft_retention(invoice)
        self.assertEqual(len(retention), 1)
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.type, "out_invoice")
        self.assertFalse(retention.number)
        self.assertFalse(invoice.iva_voucher_number)
        self.assertEqual(self._sequence_next(), before)

    def test_02_repost_does_not_duplicate_draft(self):
        invoice = self._customer_invoice()
        invoice.action_post()
        invoice.action_post()
        self.assertEqual(len(self._draft_retention(invoice)), 1)

    def test_03_draft_without_number_can_be_saved_in_form(self):
        invoice = self._customer_invoice()
        invoice.action_post()
        retention = self._draft_retention(invoice)
        with Form(retention, view=self.FORM) as form:
            form.date = retention.date
        self.assertFalse(retention.number)
        self.assertEqual(retention.state, "draft")

    def test_04_post_requires_number_then_fills_invoice(self):
        before = self._sequence_next()
        invoice = self._customer_invoice()
        invoice.action_post()
        retention = self._draft_retention(invoice)
        # For customers the amount is typed in too (auto-fill is off by
        # default), so the only thing missing here is the voucher number.
        for line in retention.retention_line_ids:
            line.retention_amount = line.iva_amount * 0.75
            line.foreign_retention_amount = line.foreign_iva_amount * 0.75
        with self.assertRaisesRegex(UserError, "Insert a number"):
            retention.action_post()
        with Form(retention, view=self.FORM) as form:
            form.number = "20261100001234"
        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(invoice.iva_voucher_number, "20261100001234")
        self.assertEqual(self._sequence_next(), before)

    def test_05_supplier_keeps_sequence_number_and_posts(self):
        before = self._sequence_next()
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.generate_iva_retention = True
        invoice.action_post()
        retention = self._draft_retention(invoice)
        self.assertEqual(retention.state, "emitted")
        self.assertRegex(retention.number, r"^\d{14}$")
        self.assertEqual(invoice.iva_voucher_number, retention.number)
        self.assertEqual(self._sequence_next(), before + 1)

    def test_06_customer_islr_draft_no_number_no_duplicate(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        invoice.generate_islr_retention = True
        before = self.env["account.retention"].get_sequence_retention("islr").number_next_actual
        invoice.with_context(move_action_post_alert=True).action_post()
        invoice.action_post()
        retention = invoice.retention_islr_line_ids.retention_id.filtered(
            lambda r: r.state != "cancel"
        )
        self.assertEqual(len(retention), 1)
        self.assertFalse(retention.number)
        self.assertFalse(invoice.islr_voucher_number)
        self.assertEqual(
            self.env["account.retention"].get_sequence_retention("islr").number_next_actual,
            before,
        )

    def test_07_customer_islr_post_requires_typed_number(self):
        invoice = self._create_invoice_islr(
            amount=1000.0, partner=self.partner_pnr_75,
            out_invoice="out_invoice", journal=self.sale_journal,
        )
        invoice.generate_islr_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()
        retention = invoice.retention_islr_line_ids.retention_id.filtered(
            lambda r: r.state != "cancel"
        )
        self.assertFalse(retention.number)
        # The amount is typed in too, so the only thing missing is the number.
        for line in retention.retention_line_ids:
            line.retention_amount = 10.0
        with self.assertRaisesRegex(UserError, "Insert a number"):
            retention.action_post()
        self.assertEqual(retention.state, "draft")

    def test_08_customer_municipal_draft_takes_no_sequence_number(self):
        sequence = self.env["account.retention"].get_sequence_retention("municipal")
        before = sequence.number_next_actual
        retention = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        self.assertFalse(retention.number)
        self.assertEqual(retention.state, "draft")
        self.assertEqual(sequence.number_next_actual, before)
        with self.assertRaisesRegex(UserError, "Insert a number"):
            retention.action_post()
