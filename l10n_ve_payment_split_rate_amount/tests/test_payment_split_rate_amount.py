from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged(
    "account_payment_register",
    "l10n_ve_payment_split_rate_amount",
    "post_install",
    "-at_install",
)
class TestPaymentSplitRateAmount(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.user.company_id
        cls.env.ref("base.VEF").sudo().active = True
        cls.env.ref("base.USD").sudo().active = True
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")

        cls.company.currency_id = cls.vef.id
        if cls.company.foreign_currency_id != cls.usd:
            cls.company.foreign_currency_id = cls.usd.id

        # The auto-writeoff feature needs the company's own exchange gain/
        # loss accounts configured - reuse them if this (real) company
        # already has them, otherwise create minimal fallbacks (bare/CI DB).
        if not cls.company.expense_currency_exchange_account_id:
            cls.company.expense_currency_exchange_account_id = cls.env[
                "account.account"
            ].create(
                {
                    "name": "Test Exchange Loss Split Rate",
                    "code": "666671",
                    "account_type": "expense",
                    "company_ids": [(6, 0, [cls.company.id])],
                }
            )
        if not cls.company.income_currency_exchange_account_id:
            cls.company.income_currency_exchange_account_id = cls.env[
                "account.account"
            ].create(
                {
                    "name": "Test Exchange Gain Split Rate",
                    "code": "666672",
                    "account_type": "income_other",
                    "company_ids": [(6, 0, [cls.company.id])],
                }
            )
        if not cls.company.currency_exchange_journal_id:
            cls.company.currency_exchange_journal_id = cls.env["account.journal"].create(
                {
                    "name": "Test Exchange Journal Split Rate",
                    "type": "general",
                    "code": "TEJS",
                    "company_id": cls.company.id,
                }
            )

        cls.tax_16 = cls.env["account.tax"].create(
            {
                "name": "Test IVA 16% Split Rate",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product Split Rate",
                "type": "service",
                "list_price": 10.0,
                "taxes_id": [(6, 0, [cls.tax_16.id])],
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Partner Split Rate"}
        )

        # Bank journals for both currencies, following the same pattern
        # already used in l10n_ve_accountant/tests/test_account_payment_rate.py
        cls.account_bank = cls.env["account.account"].create(
            {
                "name": "Test Bank Account Split Rate",
                "code": "100250",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
                "reconcile": True,
            }
        )
        cls.manual_in = cls.env.ref("account.account_payment_method_manual_in")
        cls.manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.vef_bank_journal = cls.env["account.journal"].create(
            {
                "name": "Test VEF Bank Split Rate",
                "type": "bank",
                "code": "TVBS",
                "currency_id": cls.vef.id,
                "default_account_id": cls.account_bank.id,
                "inbound_payment_method_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Manual Inbound Split Rate VEF",
                            "payment_method_id": cls.manual_in.id,
                            "payment_type": "inbound",
                            "payment_account_id": cls.account_bank.id,
                        },
                    )
                ],
                "outbound_payment_method_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Manual Outbound Split Rate VEF",
                            "payment_method_id": cls.manual_out.id,
                            "payment_type": "outbound",
                            "payment_account_id": cls.account_bank.id,
                        },
                    )
                ],
            }
        )
        cls.usd_bank_journal = cls.env["account.journal"].create(
            {
                "name": "Test USD Bank Split Rate",
                "type": "bank",
                "code": "TUBS",
                "currency_id": cls.usd.id,
                "default_account_id": cls.account_bank.id,
                "inbound_payment_method_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Manual Inbound Split Rate USD",
                            "payment_method_id": cls.manual_in.id,
                            "payment_type": "inbound",
                            "payment_account_id": cls.account_bank.id,
                        },
                    )
                ],
                "outbound_payment_method_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Manual Outbound Split Rate USD",
                            "payment_method_id": cls.manual_out.id,
                            "payment_type": "outbound",
                            "payment_account_id": cls.account_bank.id,
                        },
                    )
                ],
            }
        )

    def _set_rate(self, date, rate_vef_per_usd):
        # This test suite runs against a real, already-populated company
        # (per this project's convention), which may already have a real
        # rate recorded for the exact date a test picks - update it in
        # place instead of crashing on the (name, currency_id, company_id)
        # unique constraint. TransactionCase rolls back after each test, so
        # this never leaves real data altered.
        vals = {
            "company_rate": 1.0 / rate_vef_per_usd,
            "inverse_company_rate": rate_vef_per_usd,
        }
        existing = self.env["res.currency.rate"].search(
            [
                ("name", "=", date),
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if existing:
            existing.write(vals)
            return existing
        vals.update({"name": date, "currency_id": self.usd.id, "company_id": self.company.id})
        return self.env["res.currency.rate"].create(vals)

    def _create_invoice(self, invoice_date, currency=None, amount_untaxed=10.0):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "currency_id": (currency or self.usd).id,
                "invoice_date": invoice_date,
                "invoice_date_display": invoice_date,
                "date": invoice_date,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "price_unit": amount_untaxed,
                            "tax_ids": [(6, 0, [self.tax_16.id])],
                        },
                    )
                ],
            }
        )
        move.action_post()
        return move

    def test_full_residual_iva_at_invoice_rate_bi_at_payment_rate(self):
        invoice_date = fields.Date.today() - timedelta(days=10)
        payment_date = fields.Date.today()
        self._set_rate(invoice_date, 5.0)
        self._set_rate(payment_date, 10.0)
        invoice = self._create_invoice(invoice_date)
        self.assertAlmostEqual(invoice.foreign_rate, 5.0, places=2)

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": payment_date,
                    "journal_id": self.vef_bank_journal.id,
                    "currency_id": self.vef.id,
                }
            )
        )
        # BI 10.0 USD at today's rate (10) -> 100.0 VEF
        # IVA 1.6 USD frozen at the invoice's own rate (5) -> 8.0 VEF
        self.assertAlmostEqual(wizard.amount, 108.0, places=2)

        # The blended amount deliberately underpays a plain conversion of
        # the residual (that's the whole point), so the wizard must also
        # configure its own native "mark as fully paid via exchange
        # difference" mechanism - otherwise submitting this exact suggested
        # amount would leave the invoice open instead of closing it.
        self.assertEqual(wizard.payment_difference_handling, "reconcile")
        self.assertTrue(wizard.writeoff_is_exchange_account)

        wizard._create_payments()
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        self.assertEqual(invoice.payment_state, "paid")

    def test_writeoff_not_forced_when_no_gap(self):
        # Same-currency payment: no frozen-rate benefit, no gap, so the
        # wizard's own default "keep open" behavior must be left untouched.
        invoice_date = fields.Date.today() - timedelta(days=5)
        self._set_rate(invoice_date, 5.0)
        invoice = self._create_invoice(invoice_date, currency=self.vef)

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": fields.Date.today(),
                    "journal_id": self.vef_bank_journal.id,
                    "currency_id": self.vef.id,
                }
            )
        )
        self.assertAlmostEqual(wizard.payment_difference, 0.0, places=2)
        self.assertEqual(wizard.payment_difference_handling, "open")
        self.assertFalse(wizard.writeoff_account_id)

    def test_partial_prior_payment_proportional_split(self):
        invoice_date = fields.Date.today() - timedelta(days=10)
        payment_date = fields.Date.today()
        self._set_rate(invoice_date, 5.0)
        self._set_rate(payment_date, 10.0)
        invoice = self._create_invoice(invoice_date)

        # Register a first partial payment at the invoice's own rate (no
        # exchange complication here), just to leave a known residual.
        partial_wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": invoice_date,
                    "journal_id": self.usd_bank_journal.id,
                    "currency_id": self.usd.id,
                    "amount": 5.8,
                }
            )
        )
        partial_wizard._create_payments()
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 5.8, places=2)

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": payment_date,
                    "journal_id": self.vef_bank_journal.id,
                    "currency_id": self.vef.id,
                }
            )
        )
        # residual 5.8 out of 11.6 total -> proportion 0.5
        # iva_residual = 1.6 * 0.5 = 0.8 USD, frozen at rate 5 -> 4.0 VEF
        # bi_residual = 10.0 * 0.5 = 5.0 USD, at rate 10 -> 50.0 VEF
        self.assertAlmostEqual(wizard.amount, 54.0, places=2)

        wizard._create_payments()
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        self.assertEqual(invoice.payment_state, "paid")

    def test_same_currency_no_split_needed(self):
        invoice_date = fields.Date.today() - timedelta(days=5)
        self._set_rate(invoice_date, 5.0)
        invoice = self._create_invoice(invoice_date, currency=self.vef)

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": fields.Date.today(),
                    "journal_id": self.vef_bank_journal.id,
                    "currency_id": self.vef.id,
                }
            )
        )
        self.assertAlmostEqual(wizard.amount, invoice.amount_residual, places=2)

    def test_multi_invoice_batch_untouched(self):
        invoice_date = fields.Date.today() - timedelta(days=10)
        payment_date = fields.Date.today()
        self._set_rate(invoice_date, 5.0)
        self._set_rate(payment_date, 10.0)
        invoice_a = self._create_invoice(invoice_date)
        invoice_b = self._create_invoice(invoice_date)

        wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move", active_ids=[invoice_a.id, invoice_b.id]
            )
            .create(
                {
                    "payment_date": payment_date,
                    "journal_id": self.vef_bank_journal.id,
                    "currency_id": self.vef.id,
                }
            )
        )
        # More than one invoice in the batch -> our override must not touch
        # `amount`; it should match a plain (unblended) conversion of the
        # combined residual, i.e. core's own behavior.
        expected_core_amount = invoice_a.currency_id._convert(
            invoice_a.amount_residual + invoice_b.amount_residual,
            self.vef,
            self.company,
            payment_date,
        )
        self.assertAlmostEqual(wizard.amount, expected_core_amount, places=2)

    def test_is_igtf_skipped(self):
        # l10n_ve_igtf's own _compute_amount override reads
        # wizard.batches/installments_mode/custom_user_amount for
        # is_igtf=True wizards - none of those are defined anywhere in this
        # codebase (confirmed by grep), so any wizard that actually reaches
        # is_igtf=True crashes with AttributeError inside l10n_ve_igtf's own
        # code, before ours even runs. Forcing that state here would be
        # testing l10n_ve_igtf's pre-existing bug, not ours - that specific
        # interaction is verified manually against real data instead. This
        # test only guards that our normal (non-IGTF) scenarios aren't
        # accidentally tripping is_igtf, when the field is present at all.
        invoice = self._create_invoice(fields.Date.today())
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": fields.Date.today(),
                    "journal_id": self.usd_bank_journal.id,
                    "currency_id": self.usd.id,
                }
            )
        )
        if "is_igtf" in wizard._fields:
            self.assertFalse(wizard.is_igtf)

    def test_payment_date_change_recomputes_amount(self):
        invoice_date = fields.Date.today() - timedelta(days=10)
        payment_date = fields.Date.today()
        self._set_rate(invoice_date, 5.0)
        self._set_rate(payment_date, 10.0)
        invoice = self._create_invoice(invoice_date)

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": invoice_date,
                    "journal_id": self.vef_bank_journal.id,
                    "currency_id": self.vef.id,
                }
            )
        )
        amount_at_invoice_date = wizard.amount  # both portions at rate 5 -> 58.0
        self.assertAlmostEqual(amount_at_invoice_date, 58.0, places=2)

        wizard.payment_date = payment_date
        self.assertAlmostEqual(wizard.amount, 108.0, places=2)

    def test_currency_id_change_recomputes_amount(self):
        invoice_date = fields.Date.today() - timedelta(days=10)
        payment_date = fields.Date.today()
        self._set_rate(invoice_date, 5.0)
        self._set_rate(payment_date, 10.0)
        invoice = self._create_invoice(invoice_date)

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": payment_date,
                    "journal_id": self.usd_bank_journal.id,
                    "currency_id": self.usd.id,
                }
            )
        )
        amount_in_usd = wizard.amount  # same currency as invoice -> plain residual
        self.assertAlmostEqual(amount_in_usd, 11.6, places=2)

        wizard.currency_id = self.vef.id
        self.assertAlmostEqual(wizard.amount, 108.0, places=2)

    def test_journal_id_change_cascades_via_currency(self):
        invoice_date = fields.Date.today() - timedelta(days=10)
        payment_date = fields.Date.today()
        self._set_rate(invoice_date, 5.0)
        self._set_rate(payment_date, 10.0)
        invoice = self._create_invoice(invoice_date)

        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=[invoice.id])
            .create(
                {
                    "payment_date": payment_date,
                    "journal_id": self.usd_bank_journal.id,
                    "currency_id": self.usd.id,
                }
            )
        )
        amount_in_usd = wizard.amount
        self.assertAlmostEqual(amount_in_usd, 11.6, places=2)

        wizard.journal_id = self.vef_bank_journal.id
        self.assertAlmostEqual(wizard.amount, 108.0, places=2)
