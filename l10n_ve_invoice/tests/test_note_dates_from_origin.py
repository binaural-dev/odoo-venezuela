from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestNoteDatesFromOrigin(TransactionCase):
    """Credit/debit notes inherit document date and rate date from their
    origin; the wizards cannot change them nor target several invoices."""

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
        self.doc_date = fields.Date.today() - timedelta(days=3)
        self.rate_date = fields.Date.today() - timedelta(days=5)

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

    def test_credit_note_ignores_wizard_date(self):
        invoice = self._invoice()
        wizard = self.env["account.move.reversal"].with_context(**self._ctx(invoice)).create({
            "date": self.doc_date - timedelta(days=1),
            "journal_id": invoice.journal_id.id,
        })
        note = self.env["account.move"].browse(wizard.refund_moves()["res_id"])
        self.assertEqual(note.invoice_date_display, invoice.invoice_date_display)
        self.assertEqual(note.invoice_date, invoice.invoice_date)
        self.assertEqual(note.date, invoice.invoice_date_display)

    def test_credit_note_wizard_default_date_is_origin_date(self):
        invoice = self._invoice()
        wizard = self.env["account.move.reversal"].with_context(**self._ctx(invoice)).create({
            "journal_id": invoice.journal_id.id,
        })
        self.assertEqual(wizard.date, invoice.invoice_date_display)

    def test_debit_note_ignores_wizard_date(self):
        invoice = self._invoice()
        wizard = self.env["account.debit.note"].with_context(**self._ctx(invoice)).create({
            "date": self.doc_date - timedelta(days=1),
            "copy_lines": True,
        })
        note = self.env["account.move"].browse(wizard.create_debit()["res_id"])
        self.assertEqual(note.invoice_date_display, invoice.invoice_date_display)
        self.assertEqual(note.invoice_date, invoice.invoice_date)
        self.assertEqual(note.date, invoice.invoice_date_display)

    def test_credit_note_wizard_rejects_multiple_invoices(self):
        invoices = self._invoice() | self._invoice()
        with self.assertRaises(UserError):
            self.env["account.move.reversal"].with_context(**self._ctx(invoices)).default_get(["date"])

    def test_debit_note_wizard_rejects_multiple_invoices(self):
        invoices = self._invoice() | self._invoice()
        with self.assertRaises(UserError):
            self.env["account.debit.note"].with_context(**self._ctx(invoices)).default_get(["date"])
