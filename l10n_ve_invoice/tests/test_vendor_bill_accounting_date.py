from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import Form, TransactionCase, tagged

TODAY = "2026-03-15"


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestVendorBillAccountingDate(TransactionCase):
    """Accounting date of vendor bills stays at the registration date."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.freezer = freeze_time(TODAY)
        cls.freezer.start()
        cls.addClassCleanup(cls.freezer.stop)

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.env.ref("base.USD").id,
                "currency_foreign_id": self.env.ref("base.VEF").id,
            }
        )
        self.today = fields.Date.from_string(TODAY)
        self.partner = self.env["res.partner"].create({"name": "Vendor Test"})
        # Sin impuestos de compra: con lineas gravadas, el onchange de Form sobre un
        # registro virtual dispara un bug preexistente de l10n_ve_accountant
        # (_compute_rate_for_documents hace write() dentro de un compute y se
        # intentan crear lineas de impuesto con move_id NULL). No es parte de
        # esta funcionalidad.
        self.product = self.env["product.product"].create(
            {
                "name": "Service Test",
                "type": "service",
                "list_price": 100,
                "supplier_taxes_id": [Command.clear()],
            }
        )
        self.account = self.env["account.account"].search(
            [("company_id", "=", self.company.id), ("account_type", "=", "expense")],
            limit=1,
        )
        Journal = self.env["account.journal"]
        self.purchase_journal = Journal.create(
            {"name": "Purchase A", "code": "PUA", "type": "purchase", "company_id": self.company.id}
        )
        self.purchase_journal_b = Journal.create(
            {"name": "Purchase B", "code": "PUB", "type": "purchase", "company_id": self.company.id}
        )
        self.sale_journal = Journal.create(
            {"name": "Sale A", "code": "SLA", "type": "sale", "company_id": self.company.id}
        )

    # Helpers
    def _vals(self, move_type="in_invoice", journal=None, **extra):
        if journal is None:
            journal = self.sale_journal if move_type.startswith("out_") else self.purchase_journal
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "name": "Line",
                        "quantity": 1,
                        "price_unit": 100,
                        "account_id": self.account.id,
                        "tax_ids": [Command.set([])],
                    }
                )
            ],
        }
        vals.update(extra)
        return vals

    def _bill(self, **kwargs):
        extra = kwargs.pop("extra", {})
        return self.env["account.move"].create(self._vals(**kwargs, **extra))

    def _set_flags(self, on_registration=True, sync=False):
        self.company.write(
            {
                "vendor_bill_accounting_date_on_registration": on_registration,
                "sync_vendor_bill_accounting_date_with_invoice_date": sync,
            }
        )

    def _native_date(self, move_type, invoice_date):
        move = self.env["account.move"].new({"move_type": move_type, "invoice_date": invoice_date})
        return move._get_accounting_date(invoice_date, move._affect_tax_report())

    def _form(self, move=None, move_type="in_invoice"):
        if move:
            return Form(move)
        return Form(self.env["account.move"].with_context(default_move_type=move_type))

    # A on (default)
    def test_01_create_without_date_uses_today(self):
        for invoice_date in ("2026-02-10", "2025-03-10"):
            move = self._bill(extra={"invoice_date": invoice_date})
            self.assertEqual(move.date, self.today)

    def test_02_create_with_explicit_date_is_respected(self):
        move = self._bill(extra={"invoice_date": "2026-02-10", "date": "2026-03-01"})
        self.assertEqual(move.date, fields.Date.from_string("2026-03-01"))

    def test_03_batch_create_mixed(self):
        vals = [
            self._vals("in_invoice", invoice_date="2026-02-10"),
            self._vals("out_invoice", invoice_date="2026-02-10"),
        ]
        bill, invoice = self.env["account.move"].create(vals)
        self.assertEqual(bill.date, self.today)
        self.assertEqual(invoice.date, self._native_date("out_invoice", fields.Date.from_string("2026-02-10")))

    def test_04_form_new_bill_invoice_date_does_not_change_date(self):
        form = self._form()
        form.partner_id = self.partner
        self.assertEqual(fields.Date.to_date(form.date), self.today)
        form.invoice_date = "2026-02-10"
        self.assertEqual(fields.Date.to_date(form.date), self.today)

    def test_05_form_journal_change_keeps_date(self):
        # The purchase form requires the control number (correlative) to save
        move = self._bill(extra={"invoice_date": "2026-02-10", "correlative": "000001"})
        form = self._form(move)
        form.journal_id = self.purchase_journal_b
        # After the onchange the Form returns the date as a string
        self.assertEqual(fields.Date.to_date(form.date), self.today)
        form.date = "2026-03-02"
        form.journal_id = self.purchase_journal
        self.assertEqual(fields.Date.to_date(form.date), fields.Date.from_string("2026-03-02"))
        form.save()
        self.assertEqual(move.date, fields.Date.from_string("2026-03-02"))

    def test_06_orm_journal_and_invoice_date_change_keep_date(self):
        move = self._bill(extra={"invoice_date": "2026-02-10"})
        move.write({"journal_id": self.purchase_journal_b.id})
        self.assertEqual(move.date, self.today)
        move.write({"invoice_date": "2025-12-01"})
        self.assertEqual(move.date, self.today)

    # A off
    def test_07_a_off_b_off_native(self):
        self._set_flags(False, False)
        invoice_date = fields.Date.from_string("2026-02-10")
        move = self._bill(extra={"invoice_date": invoice_date})
        self.assertEqual(move.date, self._native_date("in_invoice", invoice_date))

    def test_08_a_off_b_on_native(self):
        self._set_flags(False, True)
        invoice_date = fields.Date.from_string("2026-02-10")
        form = self._form()
        form.partner_id = self.partner
        form.invoice_date = invoice_date
        self.assertEqual(fields.Date.to_date(form.date), self._native_date("in_invoice", invoice_date))

    # B on
    def test_09_b_on_form_syncs_with_invoice_date(self):
        self._set_flags(True, True)
        form = self._form()
        form.partner_id = self.partner
        form.invoice_date = "2026-02-10"
        self.assertEqual(fields.Date.to_date(form.date), fields.Date.from_string("2026-02-10"))

    def test_10_b_on_journal_change_does_not_touch(self):
        self._set_flags(True, True)
        move = self._bill(extra={"invoice_date": "2026-02-10", "date": "2026-03-02"})
        form = self._form(move)
        form.journal_id = self.purchase_journal_b
        self.assertEqual(fields.Date.to_date(form.date), fields.Date.from_string("2026-03-02"))

    def test_11_b_on_lock_date_does_not_sync(self):
        self._set_flags(True, True)
        self.addCleanup(self.company.write, {"tax_lock_date": self.company.tax_lock_date,
                                             "fiscalyear_lock_date": self.company.fiscalyear_lock_date})
        self.company.fiscalyear_lock_date = "2026-02-28"
        form = self._form()
        form.partner_id = self.partner
        form.invoice_date = "2026-02-10"
        self.assertEqual(fields.Date.to_date(form.date), self.today)

    def test_12_b_on_clearing_invoice_date_keeps_date(self):
        self._set_flags(True, True)
        form = self._form()
        form.partner_id = self.partner
        form.invoice_date = "2026-02-10"
        form.invoice_date = False
        self.assertEqual(fields.Date.to_date(form.date), fields.Date.from_string("2026-02-10"))

    def test_13_b_on_orm_write_does_not_sync(self):
        self._set_flags(True, True)
        move = self._bill(extra={"invoice_date": "2026-02-10"})
        move.write({"invoice_date": "2026-02-20"})
        self.assertEqual(move.date, fields.Date.from_string("2026-02-10"))

    # Lock dates
    def test_14_lock_violated_today_falls_back_to_native(self):
        self.addCleanup(self.company.write, {"fiscalyear_lock_date": self.company.fiscalyear_lock_date})
        self.company.fiscalyear_lock_date = "2026-03-20"
        invoice_date = fields.Date.from_string("2026-02-10")
        move = self._bill(extra={"invoice_date": invoice_date})
        self.assertEqual(move.date, self._native_date("in_invoice", invoice_date))
        self.assertNotEqual(move.date, self.today)

    # Other types
    def test_15_sales_untouched(self):
        invoice_date = fields.Date.from_string("2026-02-10")
        move = self._bill(move_type="out_invoice", extra={"invoice_date": invoice_date})
        self.assertEqual(move.date, self._native_date("out_invoice", invoice_date))

    def test_16_refund_and_receipt_apply(self):
        for move_type in ("in_refund", "in_receipt"):
            move = self._bill(move_type=move_type, extra={"invoice_date": "2026-02-10"})
            self.assertEqual(move.date, self.today, move_type)

    def test_17_copy_uses_today(self):
        move = self._bill(extra={"invoice_date": "2026-02-10", "date": "2026-03-02"})
        copy = move.copy()
        self.assertEqual(copy.date, self.today)

    # Posting
    def test_18_post_keeps_date_and_line_dates(self):
        move = self._bill(extra={"invoice_date": "2026-02-10"})
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, self.today)
        self.assertTrue(all(line.date == move.date for line in move.line_ids))

    def test_19_reset_to_draft_keeps_date_and_repost(self):
        # Odoo 17 no permite cambiar el diario de un asiento ya publicado una vez,
        # asi que se cambia invoice_date por ORM entre el borrador y la republicacion.
        move = self._bill(extra={"invoice_date": "2026-02-10"})
        move.action_post()
        move.button_draft()
        self.assertEqual(move.state, "draft")
        self.assertEqual(move.date, self.today)
        move.write({"invoice_date": "2026-02-20"})
        self.assertEqual(move.date, self.today)
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.date, self.today)
        self.assertTrue(all(line.date == move.date for line in move.line_ids))

    # Settings
    def test_20_settings_flags(self):
        settings = self.env["res.config.settings"].create(
            {
                "vendor_bill_accounting_date_on_registration": False,
                "sync_vendor_bill_accounting_date_with_invoice_date": True,
            }
        )
        settings.execute()
        self.assertFalse(self.env.company.vendor_bill_accounting_date_on_registration)
        self.assertTrue(self.env.company.sync_vendor_bill_accounting_date_with_invoice_date)

    def test_21_defaults_in_new_company(self):
        company = self.env["res.company"].create({"name": "Defaults Co"})
        self.assertTrue(company.vendor_bill_accounting_date_on_registration)
        self.assertFalse(company.sync_vendor_bill_accounting_date_with_invoice_date)
