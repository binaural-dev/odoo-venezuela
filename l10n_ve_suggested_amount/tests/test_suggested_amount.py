from odoo.tests import TransactionCase, tagged
from odoo import fields

import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_suggested_amount")
class TestSuggestedCustomAmount(TransactionCase):
    """
    Tests for the suggested_custom_amount computed field on account.payment.register.

    Scenario: company base currency = VEF.
    The field must only be non-zero when all three currencies are distinct:
      - Invoice currency  (source_currency_id)  ≠ company currency (VEF)
      - Payment currency  (currency_id)          ≠ company currency (VEF)
      - Invoice currency  ≠ payment currency
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_rate(self, currency, date_str, company_rate):
        """
        Create a res.currency.rate using Odoo's internal company_rate convention:
            company_rate = 1 / (VEF per foreign unit)
        e.g. 421.8772 VEF/USD → company_rate = 1/421.8772 ≈ 0.002370358009
        inverse_company_rate is derived automatically by Odoo.
        """
        return self.env["res.currency.rate"].create({
            "name": fields.Date.from_string(date_str),
            "currency_id": currency.id,
            "company_id": self.company.id,
            "company_rate": company_rate,
        })

    def _make_wizard(self, source_currency, source_amount_currency, pay_currency, pay_date, invoice_date=False):
        """
        Build an in-memory account.payment.register record via Model.new().

        Model.new() skips default_get() entirely, so the guard:
          "wizard should only be called on account.move records"
        is never raised. Fields are assigned directly and the compute
        method is called explicitly.
        """
        # Mock line_ids so the hybrid compute logic can read the invoice date
        inv_date = invoice_date or pay_date
        mock_move = self.env["account.move"].new({"invoice_date": fields.Date.from_string(inv_date)})
        mock_line = self.env["account.move.line"].new({"move_id": mock_move})

        # We must pass the correct placeholder source_amount to perfectly
        # test the same-day VEF-based calculation and future-day foreign-based calculation
        # Since the test tests the foreign currency cross-rates primarily, 
        # passing 1.0 isn't enough anymore if the dates match.
        # But for tests, we can simply say invoice_date is always yesterday unless specified, 
        # to force the foreign-currency path and keep tests simple.
        if not invoice_date:
            inv_date = fields.Date.add(fields.Date.from_string(pay_date), days=-1)
            mock_move = self.env["account.move"].new({"invoice_date": inv_date})
            mock_line = self.env["account.move.line"].new({"move_id": mock_move})

        wizard = self.env["account.payment.register"].new({
            "payment_date": fields.Date.from_string(pay_date),
            "currency_id": pay_currency.id,
            "source_currency_id": source_currency.id,
            "source_amount_currency": source_amount_currency,
            "source_amount": 1.0,  # placeholder, the compute uses source_amount_currency for future dates
            "company_id": self.company.id,
            "company_currency_id": self.vef.id,
            "line_ids": [(6, 0, mock_line.ids)]
        })
        wizard._compute_suggested_custom_amount()
        return wizard

    # ------------------------------------------------------------------
    # setUp
    # ------------------------------------------------------------------

    def setUp(self):
        super().setUp()

        self.company = self.env.ref("base.main_company")
        self.env.user.write({
            "company_ids": [(4, self.company.id)],
            "company_id": self.company.id,
        })

        # --- Currencies ---
        self.vef = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.eur = self.env.ref("base.EUR")

        # Set VEF as company base currency
        self.company.write({"currency_id": self.vef.id})

        # Ensure USD and EUR are active
        self.usd.write({"active": True})
        self.eur.write({"active": True})

        # --- Exchange rates ---
        # 2026-03-03
        self._create_rate(self.usd, "2026-03-03", 0.002370358009)  # 421.8772 VEF/USD
        self._create_rate(self.eur, "2026-03-03", 0.002026189467)  # 493.5372 VEF/EUR

        # 2026-03-05
        self._create_rate(self.usd, "2026-03-05", 0.002336829698)  # 427.9302 VEF/USD
        self._create_rate(self.eur, "2026-03-05", 0.002010366312)  # 497.4217 VEF/EUR

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_01_eur_invoice_paid_in_usd(self):
        """
        Invoice in EUR, payment in USD, company base = VEF → three distinct currencies.

        Rates on 2026-03-05:
          EUR: 497.4217 VEF/EUR
          USD: 427.9302 VEF/USD

        Expected (cross-rate): 1000 EUR × (497.4217 / 427.9302) ≈ 1162.39 USD
        """
        wizard = self._make_wizard(
            source_currency=self.eur,
            source_amount_currency=1000.00,
            pay_currency=self.usd,
            pay_date="2026-03-05",
        )
        self.assertAlmostEqual(
            wizard.suggested_custom_amount,
            1162.39,
            places=2,
            msg="EUR→USD cross-rate conversion should yield ≈ 1162.39",
        )

    def test_02_usd_invoice_paid_in_eur(self):
        """
        Invoice in USD, payment in EUR, company base = VEF → three distinct currencies.

        Rates on 2026-03-05:
          USD: 427.9302 VEF/USD
          EUR: 497.4217 VEF/EUR

        Expected (cross-rate): 1000 USD × (427.9302 / 497.4217) ≈ 860.30 EUR
        """
        wizard = self._make_wizard(
            source_currency=self.usd,
            source_amount_currency=1000.00,
            pay_currency=self.eur,
            pay_date="2026-03-05",
        )
        self.assertAlmostEqual(
            wizard.suggested_custom_amount,
            860.30,
            places=2,
            msg="USD→EUR cross-rate conversion should yield ≈ 860.30",
        )

    def test_03_same_foreign_currency(self):
        """
        Invoice and payment both in USD → source == pay currency, condition not met.
        Expected: suggested_custom_amount == 0.0
        """
        wizard = self._make_wizard(
            source_currency=self.usd,
            source_amount_currency=500.00,
            pay_currency=self.usd,
            pay_date="2026-03-05",
        )
        self.assertEqual(
            wizard.suggested_custom_amount,
            0.0,
            msg="Same foreign currency on both sides must return 0.0",
        )

    def test_04_payment_in_company_base_currency(self):
        """
        Invoice in EUR, payment in VEF (company base) → condition not met.
        Expected: suggested_custom_amount == 0.0
        """
        wizard = self._make_wizard(
            source_currency=self.eur,
            source_amount_currency=200.00,
            pay_currency=self.vef,
            pay_date="2026-03-05",
        )
        self.assertEqual(
            wizard.suggested_custom_amount,
            0.0,
            msg="Payment in company base currency (VEF) must return 0.0",
        )

    def test_05_invoice_in_company_base_currency(self):
        """
        Invoice in VEF (company base), payment in USD → source == company, condition not met.
        This closes the third 'zero' branch: source_currency_id == company_currency_id.
        Expected: suggested_custom_amount == 0.0
        """
        wizard = self._make_wizard(
            source_currency=self.vef,
            source_amount_currency=50000.00,
            pay_currency=self.usd,
            pay_date="2026-03-05",
        )
        self.assertEqual(
            wizard.suggested_custom_amount,
            0.0,
            msg="Invoice in company base currency (VEF) must return 0.0",
        )

    def test_06_result_changes_with_payment_date(self):
        """
        Using the same invoice amount (EUR→USD) but two different payment dates
        must produce two different results, proving that payment_date is actually
        used to look up exchange rates and is not ignored.

        Rates EUR on 2026-03-03: 493.5372 VEF/EUR  → cross ≈ 1169.72 USD
        Rates EUR on 2026-03-05: 497.4217 VEF/EUR  → cross ≈ 1162.39 USD
        """
        wizard_mar3 = self._make_wizard(
            source_currency=self.eur,
            source_amount_currency=1000.00,
            pay_currency=self.usd,
            pay_date="2026-03-03",
        )
        wizard_mar5 = self._make_wizard(
            source_currency=self.eur,
            source_amount_currency=1000.00,
            pay_currency=self.usd,
            pay_date="2026-03-05",
        )
        self.assertNotAlmostEqual(
            wizard_mar3.suggested_custom_amount,
            wizard_mar5.suggested_custom_amount,
            places=2,
            msg="Different payment_date must yield different suggested amounts",
        )
        self.assertAlmostEqual(
            wizard_mar3.suggested_custom_amount,
            1169.86,
            places=2,
            msg="EUR→USD on 2026-03-03 should yield ≈ 1169.86",
        )
        self.assertAlmostEqual(
            wizard_mar5.suggested_custom_amount,
            1162.39,
            places=2,
            msg="EUR→USD on 2026-03-05 should yield ≈ 1162.39",
        )
