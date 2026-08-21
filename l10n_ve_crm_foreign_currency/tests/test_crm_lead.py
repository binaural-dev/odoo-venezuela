from odoo.tests import TransactionCase, tagged
from odoo import fields
from odoo.exceptions import UserError, ValidationError


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
    - expected_revenue_foreign and recurring_revenue_foreign can never be
      negative, but 0 is allowed for both regardless of recurring_plan
      (tarea 80213: el formulario de Lead no tiene ninguno de los dos
      campos, así que convertir un Lead a Oportunidad — o fusionarlo con
      una oportunidad existente que ya tenga recurring_plan — enviaba 0 y
      quedaba bloqueado por la validación anterior de "> 0").
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

        Nota: el constraint permanente de res.company
        (_check_foreign_currency_id_required, de este módulo) rechaza
        cualquier create()/write() sin foreign_currency_id, así que la
        compañía se crea con moneda comercial y se le quita por SQL directo,
        sin pasar por el ORM.
        """
        company_without_foreign_currency = self.env["res.company"].create({
            "name": "Test Company Sin Moneda Alterna",
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
        })
        self.env.cr.execute(
            "UPDATE res_company SET foreign_currency_id = NULL WHERE id = %s",
            (company_without_foreign_currency.id,),
        )
        company_without_foreign_currency.invalidate_recordset()
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad sin moneda alterna",
            "company_id": company_without_foreign_currency.id,
            "expected_revenue_foreign": 100.0,
        })
        self.assertFalse(lead.foreign_currency_id)
        self.assertEqual(lead.expected_revenue, 0.0)

    # ------------------------------------------------------------------
    # expected_revenue_foreign: negativo rechazado; 0 permitido (tarea 80213:
    # el formulario de Lead no tiene este campo, así que convertir un Lead a
    # Oportunidad enviaba 0 y quedaba bloqueado por la validación anterior).
    # ------------------------------------------------------------------

    def test_07_expected_revenue_foreign_negative_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["crm.lead"].create({
                "name": "Oportunidad monto negativo",
                "company_id": self.company.id,
                "expected_revenue_foreign": -10.0,
            })

    def test_08_expected_revenue_foreign_zero_is_allowed(self):
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad monto cero",
            "company_id": self.company.id,
            "expected_revenue_foreign": 0.0,
        })
        self.assertEqual(lead.expected_revenue_foreign, 0.0)

    def test_08b_lead_to_opportunity_conversion_with_zero_revenue(self):
        """Escenario de la tarea 80213: convertir un Lead (sin campo de
        Ingreso Esperado en su formulario) a Oportunidad no debe bloquearse
        por expected_revenue_foreign en 0."""
        lead = self.env["crm.lead"].create({
            "name": "Lead a convertir",
            "company_id": self.company.id,
            "type": "lead",
            "expected_revenue_foreign": 0.0,
        })
        lead.write({"type": "opportunity"})
        self.assertEqual(lead.type, "opportunity")
        self.assertEqual(lead.expected_revenue_foreign, 0.0)

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

    def test_11_recurring_revenue_foreign_zero_is_allowed_with_plan(self):
        """
        Tarea 80213: con recurring_plan definido, recurring_revenue_foreign
        en 0 ya no debe rechazarse (el formulario de Lead no tiene este
        campo, así que "Fusionar con oportunidades existentes" trae
        recurring_plan de la oportunidad destino pero deja el monto en 0).
        """
        plan = self.env["crm.recurring.plan"].create({
            "name": "Mensual Test",
            "number_of_months": 1,
        })
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad con plan sin monto",
            "company_id": self.company.id,
            "expected_revenue_foreign": 100.0,
            "recurring_plan": plan.id,
            "recurring_revenue_foreign": 0.0,
        })
        self.assertEqual(lead.recurring_revenue_foreign, 0.0)

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

    # ------------------------------------------------------------------
    # expected_revenue / recurring_revenue: de solo lectura (E2)
    # ------------------------------------------------------------------

    def test_13_inverse_expected_revenue_raises_usererror(self):
        """Escribir directo a expected_revenue (moneda de compañía) debe
        rechazarse: el campo real es expected_revenue_foreign."""
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad USD",
            "company_id": self.company.id,
            "expected_revenue_foreign": 100.0,
        })
        with self.assertRaises(UserError):
            lead.write({"expected_revenue": 50000.0})

    def test_14_inverse_recurring_revenue_raises_usererror(self):
        """Escribir directo a recurring_revenue (moneda de compañía) debe
        rechazarse: el campo real es recurring_revenue_foreign."""
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad USD",
            "company_id": self.company.id,
            "expected_revenue_foreign": 100.0,
        })
        with self.assertRaises(UserError):
            lead.write({"recurring_revenue": 5000.0})

    # ------------------------------------------------------------------
    # _round_foreign sin moneda comercial configurada
    # ------------------------------------------------------------------

    def test_15_round_foreign_without_foreign_currency_returns_amount_unchanged(self):
        lead = self.env["crm.lead"].new({"name": "Sin moneda", "company_id": self.company.id})
        lead.foreign_currency_id = False
        self.assertEqual(lead._round_foreign(123.456), 123.456)

    # ------------------------------------------------------------------
    # Exenciones del constraint de monto > 0 (E1)
    # ------------------------------------------------------------------

    def test_16_lead_type_is_exempt_from_amount_check(self):
        """Un lead (type='lead', no oportunidad) no requiere monto > 0."""
        lead = self.env["crm.lead"].create({
            "name": "Lead sin monto",
            "company_id": self.company.id,
            "type": "lead",
            "expected_revenue_foreign": 0.0,
        })
        self.assertEqual(lead.type, "lead")

    def test_17_mail_gateway_context_is_exempt_from_amount_check(self):
        """Un registro creado desde la pasarela de correo/formulario web
        (contexto mail_create_nosubscribe/mail_create_nolog) no requiere
        monto > 0, aunque resuelva a type='opportunity'."""
        lead = self.env["crm.lead"].with_context(mail_create_nosubscribe=True).create({
            "name": "Oportunidad desde el gateway",
            "company_id": self.company.id,
            "type": "opportunity",
            "expected_revenue_foreign": 0.0,
        })
        self.assertEqual(lead.expected_revenue_foreign, 0.0)

    # ------------------------------------------------------------------
    # Constraints: se saltan (continue) cuando no hay moneda comercial,
    # incluso para una oportunidad real (no exenta por tipo/contexto)
    # ------------------------------------------------------------------

    def test_18_expected_revenue_check_skipped_without_foreign_currency(self):
        company_without_foreign_currency = self.env["res.company"].create({
            "name": "Test Company Sin Moneda Alterna 2",
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
        })
        self.env.cr.execute(
            "UPDATE res_company SET foreign_currency_id = NULL WHERE id = %s",
            (company_without_foreign_currency.id,),
        )
        company_without_foreign_currency.invalidate_recordset()
        # No debe lanzar aunque el monto sea 0 y sea una oportunidad real,
        # porque no hay moneda comercial a la que exigirle el monto.
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad sin moneda alterna",
            "company_id": company_without_foreign_currency.id,
            "type": "opportunity",
            "expected_revenue_foreign": 0.0,
        })
        self.assertFalse(lead.foreign_currency_id)

    def test_19_recurring_revenue_check_skipped_without_foreign_currency(self):
        company_without_foreign_currency = self.env["res.company"].create({
            "name": "Test Company Sin Moneda Alterna 3",
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
        })
        self.env.cr.execute(
            "UPDATE res_company SET foreign_currency_id = NULL WHERE id = %s",
            (company_without_foreign_currency.id,),
        )
        company_without_foreign_currency.invalidate_recordset()
        plan = self.env["crm.recurring.plan"].create({
            "name": "Mensual Test 2",
            "number_of_months": 1,
        })
        # No debe lanzar aunque haya un plan recurrente y el monto sea 0,
        # porque no hay moneda comercial a la que exigirle el monto.
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad recurrente sin moneda alterna",
            "company_id": company_without_foreign_currency.id,
            "type": "opportunity",
            "expected_revenue_foreign": 0.0,
            "recurring_plan": plan.id,
            "recurring_revenue_foreign": 0.0,
        })
        self.assertFalse(lead.foreign_currency_id)

    # ------------------------------------------------------------------
    # copy_data (E10)
    # ------------------------------------------------------------------

    def test_20_copy_data_neutralizes_recurring_without_group(self):
        """Sin crm.group_use_recurring_revenues, copiar una oportunidad debe
        neutralizar recurring_revenue_foreign (y no romper por el
        UserError de _inverse_recurring_revenue, ver E2/E10)."""
        plan = self.env["crm.recurring.plan"].create({
            "name": "Mensual Test 3",
            "number_of_months": 1,
        })
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad recurrente original",
            "company_id": self.company.id,
            "expected_revenue_foreign": 100.0,
            "recurring_plan": plan.id,
            "recurring_revenue_foreign": 10.0,
        })
        group_use_recurring_revenues = self.env.ref("crm.group_use_recurring_revenues")
        self.env.user.write({"group_ids": [(3, group_use_recurring_revenues.id)]})
        default = lead.copy_data()[0]
        self.assertEqual(default.get("recurring_revenue_foreign"), 0)

    # ------------------------------------------------------------------
    # _get_rainbowman_message (E9): usa expected_revenue_foreign (congelado)
    # en ambos lados de la comparación, no expected_revenue (recalculado).
    # ------------------------------------------------------------------

    def test_21_rainbowman_no_user_id_returns_false(self):
        lead = self.env["crm.lead"].create({
            "name": "Sin vendedor",
            "company_id": self.company.id,
            "expected_revenue_foreign": 100.0,
            "user_id": False,
        })
        self.assertFalse(lead._get_rainbowman_message())

    def test_22_rainbowman_default_false_when_nothing_matches(self):
        """Una oportunidad recién creada (no cerrada) no dispara ningún
        mensaje: cae al False final."""
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad abierta",
            "company_id": self.company.id,
            "user_id": self.env.user.id,
            "expected_revenue_foreign": 100.0,
        })
        self.assertFalse(lead._get_rainbowman_message())

    def test_23_rainbowman_first_deal_of_year_returns_message(self):
        lead = self.env["crm.lead"].create({
            "name": "Primer cierre del año",
            "company_id": self.company.id,
            "user_id": self.env.user.id,
            "type": "opportunity",
            "expected_revenue_foreign": 100.0,
        })
        lead.write({"probability": 100, "date_closed": fields.Datetime.now()})
        message = lead._get_rainbowman_message()
        self.assertTrue(message)

    def test_24_rainbowman_team_record_uses_expected_revenue_foreign_not_recalculated(self):
        """El monto histórico usado para comparar "récord de equipo" debe
        ser expected_revenue_foreign (congelado), no expected_revenue
        (recalculado a la tasa vigente) — así una devaluación entre el
        cierre anterior y el actual no dispara falsos "récords"."""
        team = self.env["crm.team"].create({
            "name": "Equipo Rainbowman",
            "company_id": self.company.id,
        })
        older_lead = self.env["crm.lead"].create({
            "name": "Cierre anterior del equipo",
            "company_id": self.company.id,
            "team_id": team.id,
            "user_id": self.env.user.id,
            "type": "opportunity",
            "expected_revenue_foreign": 1000.0,
        })
        older_lead.write({"probability": 100, "date_closed": fields.Datetime.now()})

        # Devaluación fuerte después del cierre anterior: si el método
        # comparara expected_revenue (recalculado), el segundo cierre —con
        # menos dólares pero muchos más VEF por la devaluación— se leería
        # como "récord", cuando en moneda comercial es menor.
        self._create_rate(self.usd, self.today, 0.0002)

        newer_lead = self.env["crm.lead"].create({
            "name": "Cierre actual del equipo, monto menor en USD",
            "company_id": self.company.id,
            "team_id": team.id,
            "user_id": self.env.user.id,
            "type": "opportunity",
            "expected_revenue_foreign": 500.0,
        })
        newer_lead.write({"probability": 100, "date_closed": fields.Datetime.now()})

        message = newer_lead._get_rainbowman_message()
        self.assertNotEqual(
            message,
            "Boom! Team record for the past 30 days.",
            "500 USD no es récord frente a 1000 USD, aunque en VEF (con la "
            "devaluación) sea un monto mayor.",
        )
