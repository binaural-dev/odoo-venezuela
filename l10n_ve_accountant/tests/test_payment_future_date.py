from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_payment_future_date")
class TestPaymentFutureDate(TransactionCase):
    """A payment cannot be dated after today, from the payment form (account.payment)
    nor from the register-payment wizard (account.payment.register)."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.env.user.tz = "America/Caracas"
        self.partner = self.env["res.partner"].create({"name": "Payment Future Date Partner"})
        self.account_bank = self.env["account.account"].create({
            "name": "Bank PFD",
            "code": "100901",
            "account_type": "asset_cash",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.account_income = self.env["account.account"].create({
            "name": "Income PFD",
            "code": "400901",
            "account_type": "income",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.bank_journal = self.env["account.journal"].with_context(chart_template_load=True).create({
            "name": "Bank PFD",
            "code": "BPFD",
            "type": "bank",
            "company_id": self.company.id,
            "default_account_id": self.account_bank.id,
        })
        for line in (
            self.bank_journal.inbound_payment_method_line_ids
            | self.bank_journal.outbound_payment_method_line_ids
        ).filtered(lambda l: not l.payment_account_id):
            line.payment_account_id = self.account_bank
        self.sale_journal = self.env["account.journal"].create({
            "name": "Sale PFD",
            "code": "SPFD",
            "type": "sale",
            "company_id": self.company.id,
            "default_account_id": self.account_income.id,
        })
        tax_sale = self.env["account.tax"].create({
            "name": "IVA 16% PFD sale",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
        })
        tax_purchase = self.env["account.tax"].create({
            "name": "IVA 16% PFD purchase",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
        })
        self.tax_sale = tax_sale
        self.product = self.env["product.product"].create({
            "name": "Product PFD",
            "type": "service",
            "list_price": 100,
            "taxes_id": [(6, 0, [tax_sale.id])],
            "supplier_taxes_id": [(6, 0, [tax_purchase.id])],
        })
        self.today = fields.Date.context_today(self.env["account.payment"])

    def _payment_vals(self, **extra):
        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": 100.0,
            "journal_id": self.bank_journal.id,
            "date": self.today,
        }
        vals.update(extra)
        return vals

    def _posted_invoice(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.sale_journal.id,
            "invoice_date": self.today,
            "invoice_date_display": self.today,
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100.0,
                "account_id": self.account_income.id,
                "tax_ids": [(6, 0, [self.tax_sale.id])],
            })],
        })
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _register_wizard(self, invoice, **extra):
        return self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create({"journal_id": self.bank_journal.id, **extra})

    # --- payment form (account.payment) ---

    def test_payment_dated_today_is_allowed(self):
        payment = self.env["account.payment"].create(self._payment_vals())
        self.assertEqual(payment.date, self.today)

    def test_payment_dated_in_the_past_is_allowed(self):
        payment = self.env["account.payment"].create(
            self._payment_vals(date=self.today - timedelta(days=5))
        )
        self.assertEqual(payment.date, self.today - timedelta(days=5))

    def test_payment_dated_tomorrow_is_rejected_on_create(self):
        with self.assertRaisesRegex(ValidationError, "payment date .* cannot be later than today"):
            self.env["account.payment"].create(
                self._payment_vals(date=self.today + timedelta(days=1))
            )

    def test_payment_date_moved_to_the_future_is_rejected_on_write(self):
        payment = self.env["account.payment"].create(self._payment_vals())
        with self.assertRaisesRegex(ValidationError, "payment date .* cannot be later than today"):
            payment.date = self.today + timedelta(days=1)

    def test_payment_dated_today_can_be_posted(self):
        payment = self.env["account.payment"].create(self._payment_vals())
        payment.action_post()
        self.assertNotEqual(payment.state, "draft")

    def test_payment_dated_tomorrow_is_rejected_for_vendor_payment(self):
        with self.assertRaisesRegex(ValidationError, "payment date .* cannot be later than today"):
            self.env["account.payment"].create(self._payment_vals(
                payment_type="outbound",
                partner_type="supplier",
                date=self.today + timedelta(days=1),
            ))

    def test_vendor_payment_dated_today_is_allowed(self):
        payment = self.env["account.payment"].create(self._payment_vals(
            payment_type="outbound", partner_type="supplier",
        ))
        self.assertEqual(payment.date, self.today)

    def test_payment_uses_the_user_timezone_not_utc(self):
        """A las 02:00 UTC del dia D+1 en Caracas (UTC-4) todavia son las
        22:00 del dia D: la fecha de hoy es D, no D+1 (UTC)."""
        utc_now = datetime(2026, 3, 11, 2, 0, 0)
        caracas_today = fields.Date.to_date("2026-03-10")

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_now

        # `Date.context_today` llama a `datetime.now()` de su propio modulo
        with patch("odoo.orm.fields_temporal.datetime", FrozenDatetime):
            self.assertEqual(fields.Date.context_today(self.env["account.payment"]), caracas_today)
            payment = self.env["account.payment"].create(self._payment_vals(date=caracas_today))
            self.assertEqual(payment.date, caracas_today)
            # el dia UTC ya es el 11, pero para el usuario sigue siendo el 10
            with self.assertRaisesRegex(ValidationError, "payment date .* cannot be later than today"):
                self.env["account.payment"].create(self._payment_vals(date=fields.Date.to_date("2026-03-11")))

    # --- register-payment wizard (account.payment.register) ---

    def test_wizard_with_today_creates_the_payment(self):
        invoice = self._posted_invoice()
        wizard = self._register_wizard(invoice, payment_date=self.today)
        payments = wizard._create_payments()
        self.assertEqual(payments.date, self.today)

    def test_wizard_with_a_future_date_is_rejected(self):
        invoice = self._posted_invoice()
        with self.assertRaisesRegex(ValidationError, "payment date .* cannot be later than today"):
            self._register_wizard(invoice, payment_date=self.today + timedelta(days=1))

    def test_wizard_date_moved_to_the_future_is_rejected(self):
        invoice = self._posted_invoice()
        wizard = self._register_wizard(invoice, payment_date=self.today)
        with self.assertRaisesRegex(ValidationError, "payment date .* cannot be later than today"):
            wizard.payment_date = self.today + timedelta(days=1)
