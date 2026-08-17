from odoo.tests import TransactionCase, tagged
from odoo import fields
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_crm_foreign_currency")
class TestCrmLeadForeignCurrency(TransactionCase):
    """
    Tests for the "moneda alterna" (foreign currency) fields added to crm.lead.

    Scenario: company base currency = VEF, foreign/commercial currency = USD
    (res.company.foreign_currency_id, from l10n_ve_rate).

    - expected_revenue_foreign / recurring_revenue_foreign are entered directly
      by the user, in USD, and must never be recalculated.
    - expected_revenue / recurring_revenue are computed (non-stored) from the
      *_foreign fields using the exchange rate in effect at read time.
    - expected_revenue_foreign must always be strictly positive.
    - recurring_revenue_foreign can be 0 (no recurring plan set), but must be
      strictly positive once a recurring_plan is set, and can never be
      negative either way. These two rules are independent from each other
      (review feedback: the original single constraint used an "or" that
      coupled both fields, forcing every opportunity to have a recurring
      amount even when the recurring-revenue feature isn't in use).
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
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad USD",
            "company_id": self.company.id,
            "expected_revenue_foreign": 1.0,
        })
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
            "expected_revenue_foreign": 1.0,
            "recurring_revenue_foreign": 15.0,
        })
        # 15 USD / 0.002 = 7500 VEF
        self.assertAlmostEqual(lead.recurring_revenue, 7500.0, places=2)
        self.assertEqual(lead.recurring_revenue_foreign, 15.0)

    def test_04_zero_amount_gives_zero_conversion(self):
        """
        The conversion logic itself must still degrade to 0.0 for a zero amount
        (e.g. an in-memory/unsaved record). Uses .new() on purpose: it builds an
        in-memory record without going through create()/write(), so the
        strictly-positive @api.constrains never fires here — this test isolates
        the pure conversion math from that separate business rule, which is
        covered on its own in the tests below.
        """
        lead = self.env["crm.lead"].new({"name": "Oportunidad sin monto", "company_id": self.company.id})
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

    # ------------------------------------------------------------------
    # expected_revenue_foreign: siempre estrictamente positivo
    # ------------------------------------------------------------------

    def test_07_expected_revenue_foreign_negative_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].create({
                "name": "Oportunidad monto negativo",
                "company_id": self.company.id,
                "expected_revenue_foreign": -10.0,
            })

    def test_08_expected_revenue_foreign_zero_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].create({
                "name": "Oportunidad monto cero",
                "company_id": self.company.id,
                "expected_revenue_foreign": 0.0,
            })

    # ------------------------------------------------------------------
    # recurring_revenue_foreign: 0 permitido sin recurring_plan, negativo
    # nunca permitido, y >0 obligatorio solo si hay un plan recurrente.
    # ------------------------------------------------------------------

    def test_09_recurring_revenue_foreign_zero_allowed_without_plan(self):
        """Sin recurring_plan, 0 es un valor válido (no todas las
        oportunidades tienen ingreso recurrente)."""
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad sin recurrente",
            "company_id": self.company.id,
            "expected_revenue_foreign": 100.0,
        })
        self.assertEqual(lead.recurring_revenue_foreign, 0.0)

    def test_10_recurring_revenue_foreign_negative_is_rejected(self):
        """Negativo se rechaza siempre, tenga o no recurring_plan."""
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].create({
                "name": "Oportunidad recurrente negativa",
                "company_id": self.company.id,
                "expected_revenue_foreign": 100.0,
                "recurring_revenue_foreign": -5.0,
            })

    def test_11_recurring_revenue_foreign_zero_rejected_with_plan(self):
        """Con recurring_plan definido, recurring_revenue_foreign debe ser > 0."""
        plan = self.env["crm.recurring.plan"].create({
            "name": "Mensual Test",
            "number_of_months": 1,
        })
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].create({
                "name": "Oportunidad con plan sin monto",
                "company_id": self.company.id,
                "expected_revenue_foreign": 100.0,
                "recurring_plan": plan.id,
                "recurring_revenue_foreign": 0.0,
            })

    def test_12_recurring_revenue_foreign_positive_allowed_with_plan(self):
        """Con recurring_plan y un monto positivo, no debe lanzar nada."""
        plan = self.env["crm.recurring.plan"].create({
            "name": "Mensual Test",
            "number_of_months": 1,
        })
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad con plan y monto",
            "company_id": self.company.id,
            "expected_revenue_foreign": 100.0,
            "recurring_plan": plan.id,
            "recurring_revenue_foreign": 10.0,
        })
        self.assertEqual(lead.recurring_revenue_foreign, 10.0)
