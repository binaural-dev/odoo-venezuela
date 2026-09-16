import logging
from datetime import timedelta

from odoo.tests import tagged, Form
from odoo import fields, Command

from .test_foreign_balance import TestForeignBalance

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_indexed_payments")
class TestIndexedPayments(TestForeignBalance):
    """
    Validates the indexed/non-indexed payment feature (indexed_default /
    indexaxion_payment_mode) for invoices booked in company currency (VEF) and
    paid in a foreign currency, across different foreign currencies.

    Reuses TestForeignBalance's setUp (company VEF/USD/EUR, rates, accounts,
    journals, partner, product) instead of rebuilding fixtures from scratch.
    """

    def setUp(self):
        # Deliberately skip TestForeignBalance.setUp(): it mutates
        # base.main_company's currency_id/foreign_currency_id, which
        # l10n_ve_rate forbids once that company already has account.move
        # entries (as any long-lived database will). Use a fresh company
        # instead so the same currency/rate configuration can be applied
        # without hitting "moneda alterna ya tiene movimientos contables".
        super(TestForeignBalance, self).setUp()

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_eur.active = True
        self.country_ve = self.env.ref("base.ve")

        self.company = self.env["res.company"].create({
            "name": "Indexed Payments Test Co",
            "currency_id": self.currency_vef.id,
            "foreign_currency_id": self.currency_usd.id,
            "account_fiscal_country_id": self.country_ve.id,
            "country_id": self.country_ve.id,
            # The wizard's indexed_default field is only editable when the
            # company is set to "to be agreed" (see
            # l10n_ve_accountant/wizard/account_payment_register.xml:
            # readonly="indexaxion_payment_mode != 'to_agreed' or
            # company_currency_id == currency_id"). These tests need to
            # toggle it per payment, so the company must opt into that mode.
            "indexaxion_payment_mode": "to_agreed",
        })
        self.env.user.write({"company_ids": [(4, self.company.id)], "company_id": self.company.id})

        self.invoice_date = fields.Date.today() - timedelta(days=14)
        self.payment_date = fields.Date.today()

        self.account_receivable = self.env["account.account"].create({
            "name": "Receivable",
            "code": "120000",
            "account_type": "asset_receivable",
            "company_ids": [(6, 0, [self.company.id])],
            "reconcile": True,
        })
        self.account_income = self.env["account.account"].create({
            "name": "Income",
            "code": "400000",
            "account_type": "income",
            "company_ids": [(6, 0, [self.company.id])],
        })
        self.account_bank = self.env["account.account"].create({
            "name": "Bank Account",
            "code": "100100",
            "account_type": "asset_cash",
            "company_ids": [(6, 0, [self.company.id])],
            "reconcile": True,
        })

        self.manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.manual_out = self.env.ref("account.account_payment_method_manual_out")
        self.pm_line_in = self.env["account.payment.method.line"].create({
            "name": "Manual Inbound",
            "payment_method_id": self.manual_in.id,
            "payment_type": "inbound",
            "payment_account_id": self.account_bank.id,
        })
        self.pm_line_out = self.env["account.payment.method.line"].create({
            "name": "Manual Outbound",
            "payment_method_id": self.manual_out.id,
            "payment_type": "outbound",
            "payment_account_id": self.account_bank.id,
        })

        exchange_income_account = self.env["account.account"].create({
            "name": "Exchange Gain",
            "code": "770000",
            "account_type": "income_other",
            "company_ids": [(6, 0, [self.company.id])],
        })
        exchange_expense_account = self.env["account.account"].create({
            "name": "Exchange Loss",
            "code": "670000",
            "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        exchange_journal = self.env["account.journal"].sudo().create({
            "name": "Exchange Difference",
            "code": "EXCH",
            "type": "general",
            "company_id": self.company.id,
        })
        self.company.write({
            "income_currency_exchange_account_id": exchange_income_account.id,
            "expense_currency_exchange_account_id": exchange_expense_account.id,
            "currency_exchange_journal_id": exchange_journal.id,
        })

        self.sale_journal = self.env["account.journal"].sudo().create({
            "name": "Sales Test",
            "code": "SLTST",
            "type": "sale",
            "company_id": self.company.id,
            "default_account_id": self.account_income.id,
        })

        self.partner = self.env["res.partner"].create({
            "name": "Test Partner",
            "country_id": self.country_ve.id,
            "property_account_receivable_id": self.account_receivable.id,
        })
        self.test_tax_group = self.env["account.tax.group"].create({
            "name": "Test Tax Group",
            "company_id": self.company.id,
            "country_id": self.country_ve.id,
        })
        self.test_tax = self.env["account.tax"].create({
            "name": "Test Tax 0%",
            "amount": 0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.test_tax_group.id,
        })

        self.product = self.env["product.product"].create({
            "name": "Product Test",
            "type": "service",
            "list_price": 100.0,
            "taxes_id": [(6, 0, [self.test_tax.id])],
        })

    # -- helpers (extend the parent's _set_usd_rate to any currency/date) -----

    def _set_rate(self, currency, date, rate):
        currency_rate = self.env["res.currency.rate"].search(
            [
                ("name", "=", date),
                ("currency_id", "=", currency.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if currency_rate:
            currency_rate.write({"inverse_company_rate": rate})
            return currency_rate

        return self.env["res.currency.rate"].create(
            {
                "name": date,
                "currency_id": currency.id,
                "inverse_company_rate": rate,
                "company_id": self.company.id,
            }
        )

    def _get_foreign_bank_journal(self, currency):
        journal = self.env["account.journal"].search(
            [
                ("type", "=", "bank"),
                ("currency_id", "=", currency.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if journal:
            return journal
        return self.env["account.journal"].sudo().create(
            {
                "name": f"Bank {currency.name}",
                "type": "bank",
                "code": f"BNK{currency.name}",
                "currency_id": currency.id,
                "company_id": self.company.id,
                "default_account_id": self.account_bank.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out.ids)],
            }
        )

    def _create_vef_invoice(self, amount=100.0):
        """Invoice booked directly in company currency (VEF), like the real
        case reported: a VEF invoice later paid in a foreign currency."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.currency_vef.id,
                "invoice_date": self.invoice_date,
                "invoice_date_display": self.invoice_date,
                "date": self.invoice_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": amount,
                            "account_id": self.account_income.id,
                            "tax_ids": [Command.set([self.test_tax.id])],
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _create_foreign_invoice(self, currency, amount=100.0):
        """Invoice booked in a foreign currency (USD/EUR). Odoo books the AR
        line's company-currency (VEF) balance at the invoice date's rate at
        posting time -- this is what makes a later payment converted at a
        different rate produce a real exchange difference."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "currency_id": currency.id,
                "invoice_date": self.invoice_date,
                "invoice_date_display": self.invoice_date,
                "date": self.invoice_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": amount,
                            "account_id": self.account_income.id,
                            "tax_ids": [Command.set([self.test_tax.id])],
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _register_payment(self, invoice, currency, indexed_default, amount=None):
        """Open the wizard the same way the existing l10n_ve_igtf test suite
        does: via Form.from_action + per-field .save(), so each assignment
        goes through its real onchange chain -- unlike a raw .create(vals),
        which can have a later-computed field (e.g. amount, triggered by
        indexed_default/currency_id) silently override an explicitly-passed
        value."""
        journal = self._get_foreign_bank_journal(currency)
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = journal
            pay_form.save()
            pay_form.currency_id = currency
            pay_form.save()
            pay_form.payment_date = self.payment_date
            pay_form.save()
            pay_form.indexed_default = indexed_default
            pay_form.save()
            if amount is not None:
                pay_form.amount = amount
                pay_form.save()
        return pay_form.record

    def _exchange_diff_moves(self, invoice):
        ar_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        partials = ar_lines.matched_credit_ids | ar_lines.matched_debit_ids
        return partials.mapped("exchange_move_id").filtered(lambda m: m)

    # -- tests -----------------------------------------------------------

    def test_indexed_default_uses_payment_date_rate_and_creates_exchange_diff(self):
        """indexed_default=True (default) must behave like plain Odoo. Here the
        invoice AND the payment are both in USD: the wizard amount needs no
        conversion at all (same currency), but the liquidity line still gets
        booked in VEF using the payment date's rate. Since the invoice's own
        VEF value was fixed at the invoice date's (different) rate, settling
        it fully must reproduce a normal rate mismatch -- an exchange
        difference -- exactly like standard Odoo would.

        (Paying a foreign invoice directly in company currency, VEF, is a
        different case: the wizard always reuses the invoice's own fixed VEF
        residual with no re-conversion at all, indexed or not -- so it never
        produces an exchange difference. That path is covered by the
        non-indexed tests below via the write-off/liquidity fixes.)"""
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 50.0)

        invoice = self._create_foreign_invoice(self.currency_usd, amount=100.0)
        residual_usd = invoice.amount_residual

        wizard = self._register_payment(invoice, self.currency_usd, indexed_default=True)
        conversion_date = wizard._get_conversion_date()
        self.assertEqual(
            conversion_date, self.payment_date,
            "Indexed payments must use the payment date, exactly like core Odoo.",
        )

        self.assertAlmostEqual(
            wizard.amount, residual_usd, places=2,
            msg="Same-currency payment needs no conversion for the wizard amount.",
        )

        payment = wizard._create_payments()
        self.assertIn(payment.state, ["posted", "paid"])
        self.assertEqual(invoice.amount_residual, 0.0)

        diff_moves = self._exchange_diff_moves(invoice)
        self.assertTrue(
            diff_moves,
            "Indexed payment converted at a different rate than the invoice must "
            "produce an exchange difference, same as standard Odoo.",
        )

    def test_non_indexed_uses_invoice_date_rate_and_skips_exchange_diff(self):
        """indexed_default=False must anchor the conversion to the invoice
        date's rate (reproducing the reported case: 1.011.998,59 VEF /
        1.351,52 USD invoice paid later, non-indexed) and must NOT generate an
        exchange difference, since the payment is booked at the exact same
        VEF value as the invoice."""
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 50.0)

        invoice = self._create_vef_invoice(amount=1000.0)
        residual_vef = invoice.amount_residual

        wizard = self._register_payment(invoice, self.currency_usd, indexed_default=False)
        conversion_date = wizard._get_conversion_date()
        self.assertEqual(
            conversion_date, self.invoice_date,
            "Non-indexed payments must be anchored to the invoice date.",
        )

        expected_amount = self.currency_vef._convert(
            residual_vef, self.currency_usd, self.company, self.invoice_date,
        )
        self.assertAlmostEqual(
            wizard.amount, expected_amount, places=2,
            msg="Non-indexed payment amount must be converted at the invoice date's rate, not today's.",
        )

        payment = wizard._create_payments()
        self.assertIn(payment.state, ["posted", "paid"])
        self.assertEqual(
            invoice.amount_residual, 0.0,
            "The invoice must be fully settled: the VEF value booked by the "
            "non-indexed payment must match the invoice's own VEF residual exactly.",
        )

        diff_moves = self._exchange_diff_moves(invoice)
        self.assertFalse(
            diff_moves,
            "Non-indexed payments must NOT create an exchange difference: the "
            "whole point is to book the payment at the invoice's original rate.",
        )

    def test_non_indexed_eur_payment_also_uses_invoice_date_rate(self):
        """Same non-indexed guarantee, but paying in EUR instead of USD, to
        confirm the fix is not USD-specific."""
        self._set_rate(self.currency_eur, self.invoice_date, 44.0)
        self._set_rate(self.currency_eur, self.payment_date, 55.0)

        invoice = self._create_vef_invoice(amount=880.0)
        residual_vef = invoice.amount_residual

        wizard = self._register_payment(invoice, self.currency_eur, indexed_default=False)
        self.assertEqual(wizard._get_conversion_date(), self.invoice_date)

        expected_amount = self.currency_vef._convert(
            residual_vef, self.currency_eur, self.company, self.invoice_date,
        )
        self.assertAlmostEqual(wizard.amount, expected_amount, places=2)

        payment = wizard._create_payments()
        self.assertIn(payment.state, ["posted", "paid"])
        self.assertEqual(invoice.amount_residual, 0.0)
        self.assertFalse(
            self._exchange_diff_moves(invoice),
            "EUR non-indexed payment must not create an exchange difference either.",
        )

    def test_non_indexed_overpayment_writeoff_uses_invoice_date_rate(self):
        """When overpaying (sobrante/write-off) on a non-indexed payment, the
        write-off line's VEF balance must also be converted at the invoice
        date's rate, not today's -- otherwise the sobrante alone would carry
        an inconsistent rate versus the rest of the entry."""
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 50.0)

        invoice = self._create_vef_invoice(amount=1000.0)
        residual_vef = invoice.amount_residual
        residual_usd_at_invoice_rate = self.currency_vef._convert(
            residual_vef, self.currency_usd, self.company, self.invoice_date,
        )
        overpay_extra_usd = 25.0
        overpay_amount = residual_usd_at_invoice_rate + overpay_extra_usd

        wizard = self._register_payment(
            invoice, self.currency_usd, indexed_default=False, amount=overpay_amount,
        )
        wizard.payment_difference_handling = "reconcile"
        wizard.writeoff_account_id = self.account_income

        payment_vals = wizard._create_payment_vals_from_wizard(wizard.batches[0])
        write_off_lines = payment_vals.get("write_off_line_vals", [])
        self.assertTrue(write_off_lines, "Overpayment must produce a write-off line.")

        for line_vals in write_off_lines:
            if not line_vals.get("amount_currency"):
                continue
            expected_balance = self.currency_usd._convert(
                line_vals["amount_currency"], self.currency_vef, self.company, self.invoice_date,
            )
            wrong_balance_at_payment_date = self.currency_usd._convert(
                line_vals["amount_currency"], self.currency_vef, self.company, self.payment_date,
            )
            self.assertAlmostEqual(
                line_vals["balance"], expected_balance, places=2,
                msg="Write-off balance must be converted at the invoice date's rate, not today's.",
            )
            self.assertNotAlmostEqual(
                line_vals["balance"], wrong_balance_at_payment_date, places=2,
                msg="Write-off balance must NOT match the (different) payment-date rate.",
            )

    def test_igtf_calculate_for_payment_honors_conversion_date_context(self):
        """account.payment.calculate_igtf_for_payment (l10n_ve_igtf) must use
        the l10n_ve_conversion_date context key -- set by the wizard's
        _create_payments -- instead of always the raw payment_date argument,
        so IGTF for a non-indexed payment is computed at the invoice date's
        rate rather than today's."""
        if "l10n_ve_igtf.utils" not in self.env:
            self.skipTest("l10n_ve_igtf is not installed")

        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 50.0)

        invoice = self._create_foreign_invoice(self.currency_usd, amount=100.0)
        payment = self.env["account.payment"].create({
            "amount": 50.0,
            "date": self.payment_date,
            "currency_id": self.currency_usd.id,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "journal_id": self._get_foreign_bank_journal(self.currency_usd).id,
            "payment_method_id": self.manual_in.id,
        })

        # Context wins: must match calling the same util directly with the
        # invoice date instead of today.
        igtf_with_context = payment.with_context(
            l10n_ve_conversion_date=self.invoice_date,
        ).calculate_igtf_for_payment(
            invoice, 50.0, self.currency_usd, self.payment_date, base=True,
        )
        igtf_reference_at_invoice_date = self.env["l10n_ve_igtf.utils"].calculate_igtf_for_payment(
            invoice, 50.0, self.currency_usd, self.invoice_date,
            company=self.company, base=True,
        )

        self.assertAlmostEqual(
            igtf_with_context, igtf_reference_at_invoice_date, places=2,
            msg="l10n_ve_conversion_date context must override payment_date in the IGTF calculation.",
        )
