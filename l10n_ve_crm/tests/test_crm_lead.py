from odoo.tests import TransactionCase, tagged
from odoo import fields


@tagged("post_install", "-at_install", "l10n_ve_crm")
class TestCrmLeadForeignCurrency(TransactionCase):
    """
    Tests for the "moneda alterna" (foreign currency) fields added to crm.lead.

    Scenario: company base currency = VEF, foreign/commercial currency = USD
    (res.company.foreign_currency_id, from l10n_ve_rate).

    - expected_revenue_foreign / recurring_revenue_foreign are entered directly
      by the user, in USD, and must never be recalculated.
    - expected_revenue / recurring_revenue are computed (non-stored) from the
      *_foreign fields using the exchange rate in effect at read time.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_rate(self, currency, date, company_rate):
        """
        Create a res.currency.rate using Odoo's internal company_rate convention:
            company_rate = 1 / (VEF per foreign unit)
        e.g. company_rate = 0.002 -> 1 USD = 500 VEF.
        """
        return self.env["res.currency.rate"].create({
            "name": date,
            "currency_id": currency.id,
            "company_id": self.company.id,
            "company_rate": company_rate,
        })

    # ------------------------------------------------------------------
    # setUp
    # ------------------------------------------------------------------

    def setUp(self):
        super().setUp()

        self.vef = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.usd.write({"active": True})
        self.vef.write({"active": True})

        # Compañía de prueba aislada: la real de la base puede ya tener
        # movimientos contables en la moneda alterna, y res.company.write()
        # (l10n_ve_rate) bloquea cualquier cambio a foreign_currency_id en ese
        # caso. Al crearla directamente (no vía write) evitamos ese guard y
        # no interferimos con datos existentes.
        self.company = self.env["res.company"].create({
            "name": "Test Company Moneda Alterna",
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
        })
        self.env.user.write({
            "company_ids": [(4, self.company.id)],
            "company_id": self.company.id,
        })

        self.today = fields.Date.context_today(self.env["crm.lead"])
        self.yesterday = fields.Date.subtract(self.today, days=1)
        # 1 USD = 500 VEF, en vigor desde ayer
        self.company_rate = 0.002
        self._create_rate(self.usd, self.yesterday, self.company_rate)

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_01_foreign_currency_id_follows_company(self):
        """foreign_currency_id must mirror company_id.foreign_currency_id."""
        lead = self.env["crm.lead"].create({"name": "Oportunidad USD", "company_id": self.company.id})
        self.assertEqual(lead.foreign_currency_id, self.usd)

    def test_02_expected_revenue_computed_from_foreign(self):
        """expected_revenue (VES) must be the conversion of expected_revenue_foreign (USD)."""
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad USD",
            "company_id": self.company.id,
            "expected_revenue_foreign": 200.0,
        })
        # 200 USD / 0.002 = 100000 VEF
        self.assertAlmostEqual(lead.expected_revenue, 100000.0, places=2)
        # the amount entered in the foreign currency must remain untouched
        self.assertEqual(lead.expected_revenue_foreign, 200.0)

    def test_03_recurring_revenue_computed_from_foreign(self):
        """recurring_revenue (VES) must be the conversion of recurring_revenue_foreign (USD)."""
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad USD recurrente",
            "company_id": self.company.id,
            "recurring_revenue_foreign": 15.0,
        })
        # 15 USD / 0.002 = 7500 VEF
        self.assertAlmostEqual(lead.recurring_revenue, 7500.0, places=2)
        self.assertEqual(lead.recurring_revenue_foreign, 15.0)

    def test_04_zero_amount_gives_zero(self):
        """No amount entered in the foreign currency -> converted amount is 0.0."""
        lead = self.env["crm.lead"].create({"name": "Oportunidad sin monto", "company_id": self.company.id})
        self.assertEqual(lead.expected_revenue, 0.0)
        self.assertEqual(lead.recurring_revenue, 0.0)

    def test_05_rate_change_updates_company_currency_amount_only(self):
        """
        Changing the exchange rate must change expected_revenue on the next read,
        without ever touching expected_revenue_foreign (the value the user typed).
        """
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad USD",
            "company_id": self.company.id,
            "expected_revenue_foreign": 200.0,
        })
        self.assertAlmostEqual(lead.expected_revenue, 100000.0, places=2)

        # Rate changes today: now 1 USD = 1000 VEF (company_rate = 0.001)
        self._create_rate(self.usd, self.today, 0.001)
        lead.invalidate_recordset(["expected_revenue"])

        self.assertAlmostEqual(lead.expected_revenue, 200000.0, places=2)
        self.assertEqual(
            lead.expected_revenue_foreign,
            200.0,
            msg="The amount entered in the foreign currency must never be recalculated.",
        )

    def test_06_no_foreign_currency_configured(self):
        """
        If the company has no foreign_currency_id configured, expected_revenue
        must safely default to 0.0 instead of raising.

        Nota: se crea una compañía nueva sin foreign_currency_id desde el
        create() (nunca se le hace write a ese campo) porque el write() de
        res.company en l10n_ve_rate busca account.move.line en TODA la base
        de datos (sin filtrar por compañía) para bloquear el cambio; en una
        base con movimientos reales en la moneda alterna, cualquier write a
        ese campo falla sin relación con esta funcionalidad.
        """
        company_without_foreign_currency = self.env["res.company"].create({
            "name": "Test Company Sin Moneda Alterna",
            "currency_id": self.vef.id,
        })
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad sin moneda alterna",
            "company_id": company_without_foreign_currency.id,
            "expected_revenue_foreign": 100.0,
        })
        self.assertFalse(lead.foreign_currency_id)
        self.assertEqual(lead.expected_revenue, 0.0)
