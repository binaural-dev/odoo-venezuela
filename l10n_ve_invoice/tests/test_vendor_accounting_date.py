from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestVendorAccountingDate(TransactionCase):
    """With `block_invoice_display_date_upper_than_date` (enabled by default),
    the accounting date of a vendor document cannot be earlier than its
    invoice date."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.partner = self.env["res.partner"].create({"name": "Test VAD Partner"})
        self.account_revenue = self.env["account.account"].create(
            {
                "name": "Revenue VAD",
                "code": "982001",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_expense = self.env["account.account"].create(
            {
                "name": "Expense VAD",
                "code": "682001",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.journal_purchase = self.env["account.journal"].create(
            {
                "name": "Purchase VAD Journal",
                "type": "purchase",
                "code": "VADP",
                "company_id": self.company.id,
                "default_account_id": self.account_expense.id,
            }
        )
        self.journal_sale = self.env["account.journal"].create(
            {
                "name": "Sale VAD Journal",
                "type": "sale",
                "code": "VADS",
                "company_id": self.company.id,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.product = self.env["product.product"].create(
            {"name": "Test Product VAD", "type": "service", "list_price": 100}
        )
        self.today = fields.Date.context_today(self.env["account.move"])

    def _create_move(self, move_type, journal, invoice_date_display, date):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "journal_id": journal.id,
                "invoice_date": invoice_date_display,
                "invoice_date_display": invoice_date_display,
                "date": date,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {"product_id": self.product.id, "quantity": 1, "price_unit": 100},
                    )
                ],
            }
        )

    def test_company_setting_is_enabled_by_default(self):
        defaults = self.env["res.company"].default_get(
            ["block_invoice_display_date_upper_than_date"]
        )
        self.assertTrue(defaults["block_invoice_display_date_upper_than_date"])

    def test_company_setting_off_does_not_block(self):
        self.company.block_invoice_display_date_upper_than_date = False
        bill = self._create_move(
            "in_invoice",
            self.journal_purchase,
            self.today,
            self.today - timedelta(days=1),
        )
        self.assertEqual(bill.date, self.today - timedelta(days=1))

    def test_vendor_credit_note_blocks(self):
        with self.assertRaisesRegex(ValidationError, "cannot be greater than the accounting"):
            self._create_move(
                "in_refund",
                self.journal_purchase,
                self.today,
                self.today - timedelta(days=1),
            )

    def test_editing_accounting_date_before_invoice_date_blocks(self):
        bill = self._create_move(
            "in_invoice", self.journal_purchase, self.today, self.today
        )
        with self.assertRaisesRegex(ValidationError, "cannot be greater than the accounting"):
            bill.date = self.today - timedelta(days=1)

    def test_editing_invoice_date_after_accounting_date_blocks(self):
        bill = self._create_move(
            "in_invoice", self.journal_purchase, self.today, self.today
        )
        with self.assertRaisesRegex(ValidationError, "cannot be greater than the accounting"):
            bill.write(
                {
                    "invoice_date_display": self.today + timedelta(days=1),
                    "date": self.today,
                }
            )

    def test_accounting_date_equal_to_invoice_date_is_allowed(self):
        bill = self._create_move(
            "in_invoice", self.journal_purchase, self.today, self.today
        )
        self.assertEqual(bill.date, bill.invoice_date_display)

    def test_accounting_date_after_invoice_date_is_allowed(self):
        bill = self._create_move(
            "in_invoice",
            self.journal_purchase,
            self.today - timedelta(days=3),
            self.today,
        )
        self.assertEqual(bill.date, self.today)
        self.assertEqual(bill.invoice_date_display, self.today - timedelta(days=3))

    def test_customer_invoice_is_not_affected(self):
        invoice = self._create_move(
            "out_invoice",
            self.journal_sale,
            self.today,
            self.today - timedelta(days=1),
        )
        self.assertEqual(invoice.date, self.today - timedelta(days=1))

    def test_accounting_date_in_future_blocks(self):
        with self.assertRaisesRegex(ValidationError, "cannot be greater than today"):
            self._create_move(
                "in_invoice",
                self.journal_purchase,
                self.today,
                self.today + timedelta(days=1),
            )

    def test_accounting_date_in_future_with_setting_off_is_allowed(self):
        self.company.block_invoice_display_date_upper_than_date = False
        bill = self._create_move(
            "in_invoice",
            self.journal_purchase,
            self.today,
            self.today + timedelta(days=1),
        )
        self.assertEqual(bill.date, self.today + timedelta(days=1))
