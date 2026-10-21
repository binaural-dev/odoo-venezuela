from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestVendorBillAccountingDate(TransactionCase):
    """Back-dated vendor bills must use today as accounting date (not period end)."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        # Localization taxes require a foreign currency on the company
        self.company.write(
            {
                "currency_id": self.env.ref("base.USD").id,
                "currency_foreign_id": self.env.ref("base.VEF").id,
            }
        )
        self.today = fields.Date.context_today(self.env.user)
        self.partner = self.env["res.partner"].create({"name": "Vendor Date Test"})
        self.product = self.env["product.product"].create(
            {"name": "Service Date Test", "type": "service", "list_price": 100}
        )
        self.purchase_journal = self.env["account.journal"].create(
            {
                "name": "Purchase Date Test",
                "code": "PDT",
                "type": "purchase",
                "company_id": self.company.id,
            }
        )
        self.sale_journal = self.env["account.journal"].create(
            {
                "name": "Sale Date Test",
                "code": "SDT",
                "type": "sale",
                "company_id": self.company.id,
            }
        )

    def _vals(self, move_type, invoice_date, journal=None, **extra):
        if journal is None:
            journal = (
                self.sale_journal
                if move_type.startswith("out_")
                else self.purchase_journal
            )
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_date": invoice_date,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 100,
                    }
                )
            ],
        }
        vals.update(extra)
        return vals

    def _create(self, move_type, invoice_date, **extra):
        return self.env["account.move"].create(
            self._vals(move_type, invoice_date, **extra)
        )

    def _native_date(self, move):
        return move._get_accounting_date(move.invoice_date, move._affect_tax_report())

    def _previous_month_date(self):
        return (self.today.replace(day=1) - timedelta(days=1)).replace(day=1)

    def test_01_previous_month_uses_today(self):
        move = self._create("in_invoice", self._previous_month_date())
        self.assertEqual(move.date, self.today)

    def test_02_previous_year_uses_today(self):
        move = self._create("in_invoice", self.today.replace(year=self.today.year - 1, day=1))
        self.assertEqual(move.date, self.today)

    def test_03_current_month_and_future(self):
        if self.today.day > 1:
            move = self._create("in_invoice", self.today.replace(day=1))
            self.assertEqual(move.date, self.today)
        future = self.today + timedelta(days=5)
        move = self._create("in_invoice", future)
        self.assertEqual(move.date, future)

    def test_04_virtual_record_uses_today(self):
        vals = self._vals("in_invoice", self._previous_month_date())
        vals.pop("invoice_line_ids")
        move = self.env["account.move"].new(vals)
        self.assertEqual(move.date, self.today)

    def test_05_skip_setting_keeps_native(self):
        self.company.skip_vendor_bill_today_accounting_date = True
        move = self._create("in_invoice", self._previous_month_date())
        self.assertEqual(move.date, self._native_date(move))

    def test_06_customer_invoice_unchanged(self):
        invoice_date = self._previous_month_date()
        move = self._create("out_invoice", invoice_date)
        self.assertEqual(move.date, invoice_date)

    def test_07_vendor_refund_uses_today(self):
        move = self._create("in_refund", self._previous_month_date())
        self.assertEqual(move.date, self.today)

    def test_08_lock_date_violated_keeps_native(self):
        old_lock = self.company.fiscalyear_lock_date
        self.addCleanup(
            lambda: self.company.write({"fiscalyear_lock_date": old_lock})
        )
        self.company.fiscalyear_lock_date = self.today
        move = self._create("in_invoice", self._previous_month_date())
        self.assertNotEqual(move.date, self.today)
        self.assertEqual(move.date, self._native_date(move))

    def test_09_manual_date_is_preserved(self):
        move = self._create("in_invoice", self._previous_month_date())
        manual = self.today - timedelta(days=1)
        move.date = manual
        move.flush_recordset()
        move.invalidate_recordset()
        self.assertEqual(move.date, manual)

    def test_10_post_keeps_line_dates_in_sync(self):
        move = self._create("in_invoice", self._previous_month_date())
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, self.today)
        self.assertTrue(move.line_ids)
        self.assertTrue(all(line.date == move.date for line in move.line_ids))
