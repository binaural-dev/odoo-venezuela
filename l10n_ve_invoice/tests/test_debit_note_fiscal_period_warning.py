from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestDebitNoteFiscalPeriodWarning(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company.currency_id = self.currency_vef
        self.company.foreign_currency_id = self.currency_usd

        self.partner = self.env["res.partner"].create({"name": "Test DN Period Partner"})

        self.account_expense = self.env["account.account"].create(
            {
                "name": "Expense DN Period",
                "code": "580002",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.journal_purchase = self.env["account.journal"].create(
            {
                "name": "Purchase DN Period Journal",
                "type": "purchase",
                "code": "DNPJP",
                "company_id": self.company.id,
                "default_account_id": self.account_expense.id,
            }
        )
        self.product = self.env["product.product"].create(
            {"name": "Test Product DN Period", "type": "service", "list_price": 100}
        )

    def _create_posted_bill(self, invoice_date_display, date=None):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": invoice_date_display,
                "invoice_date_display": invoice_date_display,
                "date": date or invoice_date_display,
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": 100})
                ],
            }
        )
        bill.action_post()
        return bill

    def _wizard(self, moves, note_date):
        # `.new()` WITHOUT `active_model`/`active_id` in context -- avoids
        # `account.debit.note.default_get`'s "You can only debit posted
        # moves" gate (irrelevant here, this only exercises the fiscal
        # period compute) so the test can also cover a DRAFT customer
        # invoice.
        wizard = self.env["account.debit.note"].new({"date": note_date})
        wizard.move_ids = moves
        return wizard

    def test_same_period_no_warning(self):
        bill = self._create_posted_bill(fields.Date.from_string("2026-01-15"))
        wizard = self._wizard(bill, fields.Date.from_string("2026-01-20"))
        self.assertFalse(wizard.l10n_ve_out_of_fiscal_period_warning)

    def test_different_period_warns(self):
        bill = self._create_posted_bill(fields.Date.from_string("2026-01-15"))
        wizard = self._wizard(bill, fields.Date.from_string("2026-03-01"))
        self.assertTrue(wizard.l10n_ve_out_of_fiscal_period_warning)

    def test_uses_invoice_date_display_not_accounting_date(self):
        # Bill issued in January (`invoice_date_display`, the real fiscal
        # date) but posted/accounted in March (`date`) -- a Debit Note
        # dated in JANUARY must NOT warn: it matches the bill's declared
        # fiscal period, even though it differs from the bill's own
        # accounting `date`.
        bill = self._create_posted_bill(
            invoice_date_display=fields.Date.from_string("2026-01-15"),
            date=fields.Date.from_string("2026-03-01"),
        )
        wizard = self._wizard(bill, fields.Date.from_string("2026-01-20"))
        self.assertFalse(wizard.l10n_ve_out_of_fiscal_period_warning)

    def test_customer_invoice_no_warning(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.from_string("2026-01-15"),
                "date": fields.Date.from_string("2026-01-15"),
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": 100})
                ],
            }
        )
        wizard = self._wizard(invoice, fields.Date.from_string("2026-03-01"))
        self.assertFalse(wizard.l10n_ve_out_of_fiscal_period_warning)

    def test_created_note_keeps_origin_rate_date(self):
        # `invoice_date` ("Rate Date", l10n_ve_accountant/l10n_ve_invoice)
        # must stay the ORIGIN's -- otherwise the note prices at a
        # DIFFERENT exchange rate than the bill it corrects, manufacturing
        # a spurious exchange difference between two documents that are
        # really the same transaction.
        bill = self._create_posted_bill(fields.Date.from_string("2026-01-15"))
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=[bill.id], active_id=bill.id
        ).create({"date": fields.Date.from_string("2026-03-05")})
        action = wizard.create_debit()
        note = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(note.invoice_date, bill.invoice_date)

    def test_created_note_own_fiscal_date_is_wizard_date(self):
        # `invoice_date_display` (the note's OWN declared fiscal date,
        # what `_get_accounting_date_source` derives `date` from) must be
        # the wizard's own `date` -- NOT silently inherited from the
        # origin via `copy()`.
        bill = self._create_posted_bill(fields.Date.from_string("2026-01-15"))
        note_date = fields.Date.from_string("2026-03-05")
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=[bill.id], active_id=bill.id
        ).create({"date": note_date})
        action = wizard.create_debit()
        note = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(note.invoice_date_display, note_date)
        self.assertEqual(note.date, note_date)
