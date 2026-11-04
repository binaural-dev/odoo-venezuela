from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestNoteDatesFromOrigin(TransactionCase):
    """Credit/debit notes keep the origin's rate date, take a document date
    between the origin's and today (default today) and target one invoice."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.partner = self.env["res.partner"].create({"name": "Note Dates Partner"})
        account = self.env["account.account"].create({
            "name": "Revenue ND dates",
            "code": "980101",
            "account_type": "income",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.journal = self.env["account.journal"].create({
            "name": "Sale ND dates",
            "type": "sale",
            "code": "NDDT",
            "company_id": self.company.id,
            "default_account_id": account.id,
        })
        self.tax = self.env["account.tax"].create({
            "name": "IVA 16% ND dates",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
        })
        self.product = self.env["product.product"].create({
            "name": "Product ND dates",
            "type": "service",
            "list_price": 100,
            "taxes_id": [(6, 0, [self.tax.id])],
        })
        today = fields.Date.context_today(self.env["account.move"])
        self.doc_date = today - timedelta(days=3)
        self.rate_date = today - timedelta(days=5)

    def _invoice(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": self.rate_date,
            "invoice_date_display": self.doc_date,
            "date": self.doc_date,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "tax_ids": [(6, 0, [self.tax.id])],
            })],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _ctx(self, moves):
        return {"active_model": "account.move", "active_ids": moves.ids, "active_id": moves[:1].id}

    def _today(self):
        return fields.Date.context_today(self.env["account.move"])

    def _credit_wizard(self, invoice, **vals):
        return self.env["account.move.reversal"].with_context(**self._ctx(invoice)).create({
            "journal_id": invoice.journal_id.id,
            **vals,
        })

    def _debit_wizard(self, invoice, **vals):
        return self.env["account.debit.note"].with_context(**self._ctx(invoice)).create({
            "copy_lines": True,
            **vals,
        })

    def test_wizards_default_date_is_today(self):
        invoice = self._invoice()
        self.assertEqual(self._credit_wizard(invoice).date, self._today())
        self.assertEqual(self._debit_wizard(invoice).date, self._today())

    def test_credit_note_takes_wizard_date_and_origin_rate_date(self):
        invoice = self._invoice()
        note_date = self.doc_date + timedelta(days=1)
        wizard = self._credit_wizard(invoice, date=note_date)
        note = self.env["account.move"].browse(wizard.refund_moves()["res_id"])
        self.assertEqual(note.invoice_date_display, note_date)
        self.assertEqual(note.date, note_date)
        self.assertEqual(note.invoice_date, invoice.invoice_date)

    def test_debit_note_takes_wizard_date_and_origin_rate_date(self):
        invoice = self._invoice()
        note_date = self.doc_date + timedelta(days=1)
        note = self.env["account.move"].browse(self._debit_wizard(invoice, date=note_date).create_debit()["res_id"])
        self.assertEqual(note.invoice_date_display, note_date)
        self.assertEqual(note.date, note_date)
        self.assertEqual(note.invoice_date, invoice.invoice_date)

    def test_note_on_origin_date_is_allowed(self):
        invoice = self._invoice()
        wizard = self._credit_wizard(invoice, date=self.doc_date)
        note = self.env["account.move"].browse(wizard.refund_moves()["res_id"])
        self.assertEqual(note.invoice_date_display, self.doc_date)

    def test_credit_note_wizard_rejects_date_before_origin(self):
        invoice = self._invoice()
        wizard = self._credit_wizard(invoice, date=self.doc_date - timedelta(days=1))
        with self.assertRaisesRegex(ValidationError, "earlier than the date of the original"):
            wizard.refund_moves()

    def test_credit_note_wizard_rejects_future_date(self):
        invoice = self._invoice()
        wizard = self._credit_wizard(invoice, date=self._today() + timedelta(days=1))
        with self.assertRaisesRegex(ValidationError, "later than today"):
            wizard.refund_moves()

    def test_debit_note_wizard_rejects_date_before_origin(self):
        invoice = self._invoice()
        wizard = self._debit_wizard(invoice, date=self.doc_date - timedelta(days=1))
        with self.assertRaisesRegex(ValidationError, "earlier than the date of the original"):
            wizard.create_debit()

    def test_debit_note_wizard_rejects_future_date(self):
        invoice = self._invoice()
        wizard = self._debit_wizard(invoice, date=self._today() + timedelta(days=1))
        with self.assertRaisesRegex(ValidationError, "later than today"):
            wizard.create_debit()

    def test_posting_note_edited_before_origin_is_blocked(self):
        invoice = self._invoice()
        note = self.env["account.move"].browse(self._credit_wizard(invoice).refund_moves()["res_id"])
        note.invoice_date_display = self.doc_date - timedelta(days=1)
        with self.assertRaisesRegex(ValidationError, "earlier than the date of the original"):
            note.action_post()

    def test_credit_note_wizard_rejects_multiple_invoices(self):
        invoices = self._invoice() | self._invoice()
        with self.assertRaisesRegex(UserError, "single invoice"):
            self.env["account.move.reversal"].with_context(**self._ctx(invoices)).default_get(["date"])

    def test_debit_note_wizard_rejects_multiple_invoices(self):
        invoices = self._invoice() | self._invoice()
        with self.assertRaisesRegex(UserError, "single document"):
            self.env["account.debit.note"].with_context(**self._ctx(invoices)).default_get(["date"])

    def test_posting_note_with_rate_date_different_from_origin_is_blocked(self):
        invoice = self._invoice()
        note = self.env["account.move"].browse(self._credit_wizard(invoice).refund_moves()["res_id"])
        note.invoice_date = invoice.invoice_date - timedelta(days=1)
        with self.assertRaisesRegex(ValidationError, "must be equal to the one of the original"):
            note.action_post()

    def test_note_accounting_date_cannot_be_earlier_than_its_invoice_date(self):
        invoice = self._invoice()
        note = self.env["account.move"].browse(self._credit_wizard(invoice).refund_moves()["res_id"])
        with self.assertRaisesRegex(ValidationError, "accounting date .* cannot be earlier"):
            note.date = note.invoice_date_display - timedelta(days=1)

    def test_debit_note_accounting_date_cannot_be_earlier_than_its_invoice_date(self):
        invoice = self._invoice()
        note = self.env["account.move"].browse(self._debit_wizard(invoice).create_debit()["res_id"])
        with self.assertRaisesRegex(ValidationError, "accounting date .* cannot be earlier"):
            note.date = note.invoice_date_display - timedelta(days=1)

