from odoo.tests import TransactionCase, tagged
from odoo import fields


@tagged("post_install", "-at_install", "l10n_ve_crm")
class TestCrmTeamForeignCurrency(TransactionCase):
    """
    Tests for the "moneda alterna" (foreign currency) fields added to crm.team.

    Scenario: company base currency = VEF, foreign/commercial currency = USD
    (res.company.foreign_currency_id, from l10n_ve_rate).

    - invoiced_target_foreign is entered directly by the manager, in USD, and
      must never be recalculated.
    - invoiced_target (VES) is computed from invoiced_target_foreign using the
      exchange rate in effect at read time (it's a forward-looking goal, so
      "today's rate" is the correct behavior here).
    - invoiced_foreign (VES) sums foreign_untaxed_total from posted/paid
      invoices of the current month for the team, which is already frozen
      per-invoice at the historical rate (no re-conversion needed/wanted).
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

    def _create_invoice(self, team, amount_foreign, date, payment_state="paid", move_type="out_invoice"):
        """
        Inserta una fila mínima directamente en account_move para poder probar
        la agregación SQL de _compute_invoiced_foreign (filtro por team_id,
        rango de fecha, state y payment_state) sin necesitar un plan de
        cuentas completo: no es objetivo de este test validar la
        contabilización real, sino nuestra query de suma.

        amount_foreign siempre se inserta positivo, igual que el
        foreign_untaxed_total real (que no tiene signo, ni para
        out_invoice ni para out_refund) — el neteo de las notas de
        crédito lo debe hacer la query, no el dato insertado.
        """
        journal = self.env["account.journal"].search([], limit=1)
        self.env.cr.execute(
            """
            INSERT INTO account_move
                (journal_id, currency_id, state, move_type, auto_post, date,
                 team_id, payment_state, foreign_untaxed_total, company_id)
            VALUES (%s, %s, 'posted', %s, 'no', %s, %s, %s, %s, %s)
            """,
            (
                journal.id,
                self.company.currency_id.id,
                move_type,
                date,
                team.id,
                payment_state,
                amount_foreign,
                self.company.id,
            ),
        )

    # ------------------------------------------------------------------
    # setUp
    # ------------------------------------------------------------------

    def setUp(self):
        super().setUp()

        self.vef = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.usd.write({"active": True})
        self.vef.write({"active": True})

        # Compañía de prueba aislada: ver test_crm_lead.py para el motivo
        # (write() a foreign_currency_id en l10n_ve_rate bloquea el cambio si
        # existen account.move.line en toda la base con esa moneda).
        self.company = self.env["res.company"].create({
            "name": "Test Company Moneda Alterna CRM Team",
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
        })

        self.today = fields.Date.context_today(self.env["crm.team"])
        self.yesterday = fields.Date.subtract(self.today, days=1)
        # 1 USD = 500 VEF, en vigor desde ayer
        self.company_rate = 0.002
        self._create_rate(self.usd, self.yesterday, self.company_rate)

        self.team = self.env["crm.team"].create({
            "name": "Equipo Test",
            "company_id": self.company.id,
        })

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_01_foreign_currency_id_follows_company(self):
        """foreign_currency_id must mirror company_id.foreign_currency_id."""
        self.assertEqual(self.team.foreign_currency_id, self.usd)

    def test_02_no_company_falls_back_to_env_company(self):
        """crm.team without company_id (shared team) must fall back to env.company."""
        team = self.env["crm.team"].create({"name": "Equipo sin compañía"})
        self.assertEqual(team.foreign_currency_id, self.env.company.foreign_currency_id)

    def test_03_invoiced_target_computed_from_foreign(self):
        """invoiced_target (VES) must be the conversion of invoiced_target_foreign (USD)."""
        self.team.invoiced_target_foreign = 100.0
        # 100 USD / 0.002 = 50000 VEF
        self.assertAlmostEqual(self.team.invoiced_target, 50000.0, places=2)
        self.assertEqual(self.team.invoiced_target_foreign, 100.0)

    def test_04_invoiced_target_zero_without_foreign_currency(self):
        """No foreign_currency_id configured -> invoiced_target degrades to 0.0."""
        company_without_foreign_currency = self.env["res.company"].create({
            "name": "Test Company Sin Moneda Alterna",
            "currency_id": self.vef.id,
        })
        team = self.env["crm.team"].create({
            "name": "Equipo sin moneda alterna",
            "company_id": company_without_foreign_currency.id,
            "invoiced_target_foreign": 50.0,
        })
        self.assertFalse(team.foreign_currency_id)
        self.assertEqual(team.invoiced_target, 0.0)

    def test_05_invoiced_target_reflects_todays_rate_immediately(self):
        """
        Unlike invoiced_foreign (historical, frozen per-invoice), invoiced_target
        is a forward-looking goal: it must always use today's rate, and change
        immediately when the rate changes, without ever touching the amount
        entered in the foreign currency.
        """
        self.team.invoiced_target_foreign = 100.0
        self.assertAlmostEqual(self.team.invoiced_target, 50000.0, places=2)

        # Nueva tasa hoy: 1 USD = 1000 VEF
        self._create_rate(self.usd, self.today, 0.001)
        self.team.invalidate_recordset(["invoiced_target"])

        self.assertAlmostEqual(self.team.invoiced_target, 100000.0, places=2)
        self.assertEqual(
            self.team.invoiced_target_foreign,
            100.0,
            msg="The amount entered in the foreign currency must never be recalculated.",
        )

    def test_06_update_invoiced_target_writes_foreign_field(self):
        """update_invoiced_target (called by the kanban widget) must write
        invoiced_target_foreign, since invoiced_target is no longer stored."""
        self.team.update_invoiced_target(250)
        self.assertEqual(self.team.invoiced_target_foreign, 250.0)

    def test_07_invoiced_foreign_sums_current_month_paid_invoices(self):
        """invoiced_foreign must sum foreign_untaxed_total of posted/paid
        invoices of the team for the current month."""
        self._create_invoice(self.team, 200.0, self.today)
        self._create_invoice(self.team, 50.0, self.today)
        self.team.invalidate_recordset(["invoiced_foreign"])
        self.assertAlmostEqual(self.team.invoiced_foreign, 250.0, places=2)

    def test_08_invoiced_foreign_ignores_unpaid_and_other_teams(self):
        """Unpaid invoices and invoices from other teams must not be counted."""
        other_team = self.env["crm.team"].create({
            "name": "Otro equipo",
            "company_id": self.company.id,
        })
        self._create_invoice(self.team, 200.0, self.today, payment_state="not_paid")
        self._create_invoice(other_team, 300.0, self.today, payment_state="paid")
        self.team.invalidate_recordset(["invoiced_foreign"])
        self.assertEqual(self.team.invoiced_foreign, 0.0)

    def test_09_invoiced_foreign_zero_without_invoices(self):
        """No invoices this month -> invoiced_foreign is 0.0."""
        self.assertEqual(self.team.invoiced_foreign, 0.0)

    def test_10_invoiced_foreign_on_new_record_is_zero(self):
        """An unsaved (.new()) team has no ids -> invoiced_foreign must not
        raise and must default to 0.0 (same guard as core's _compute_invoiced)."""
        team = self.env["crm.team"].new({"name": "Equipo sin guardar"})
        self.assertEqual(team.invoiced_foreign, 0.0)

    def test_11_invoiced_foreign_subtracts_credit_notes(self):
        """
        foreign_untaxed_total no tiene signo (positivo tanto para out_invoice
        como para out_refund, igual que su análogo amount_untaxed). La query
        debe restar explícitamente las notas de crédito, no sumarlas: un
        equipo que facturó 200 y emitió una NC de 50 debe mostrar 150, no 250.
        """
        self._create_invoice(self.team, 200.0, self.today, move_type="out_invoice")
        self._create_invoice(self.team, 50.0, self.today, move_type="out_refund")
        self.team.invalidate_recordset(["invoiced_foreign"])
        self.assertAlmostEqual(self.team.invoiced_foreign, 150.0, places=2)
