from odoo.tests import TransactionCase, tagged
from odoo import fields

from odoo.addons.l10n_ve_crm_foreign_currency import hooks


@tagged("post_install", "-at_install", "l10n_ve_crm_foreign_currency")
class TestPostInitHook(TransactionCase):
    """
    Tests for post_init_hook: backfills expected_revenue_foreign,
    recurring_revenue_foreign (crm.lead) and invoiced_target_foreign
    (crm.team) from the historical amounts that were stored in company
    currency before this module turned those fields into compute=/store=False.

    Since those old columns are only ever populated by real historical data
    (never by our own compute, which starts every record at 0), the tests
    simulate a "pre-migration" record by writing the old column directly via
    SQL — the same technique already used in test_crm_team.py to insert
    account_move rows without going through the full accounting flow.
    """

    def _create_rate(self, currency, date, company_rate):
        return self.env["res.currency.rate"].create({
            "name": date,
            "currency_id": currency.id,
            "company_id": self.company.id,
            "company_rate": company_rate,
        })

    def setUp(self):
        super().setUp()

        self.vef = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.usd.write({"active": True})
        self.vef.write({"active": True})

        self.company = self.env["res.company"].create({
            "name": "Test Company Backfill",
            "currency_id": self.vef.id,
            "foreign_currency_id": self.usd.id,
        })

        self.today = fields.Date.context_today(self.env["crm.lead"])
        self.yesterday = fields.Date.subtract(self.today, days=1)
        # 1 USD = 500 VEF, en vigor desde ayer (cubre "hoy", que es cuando
        # se crean los registros de este test)
        self.company_rate = 0.002
        self._create_rate(self.usd, self.yesterday, self.company_rate)

    def test_01_backfills_crm_lead_expected_and_recurring_revenue(self):
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad histórica",
            "company_id": self.company.id,
            "expected_revenue_foreign": 1.0,
        })
        # Simula un registro pre-existente a la instalación del módulo: el
        # monto histórico vivía en las columnas viejas (en VEF), y
        # expected_revenue_foreign/recurring_revenue_foreign nunca se
        # llenaron porque el módulo no existía todavía.
        self.env.cr.execute(
            """
            UPDATE crm_lead
            SET expected_revenue = %s, recurring_revenue = %s,
                expected_revenue_foreign = 0, recurring_revenue_foreign = 0
            WHERE id = %s
            """,
            (100000.0, 5000.0, lead.id),
        )
        lead.invalidate_recordset()

        hooks.post_init_hook(self.env)
        lead.invalidate_recordset()

        # 100000 VEF * 0.002 = 200 USD ; 5000 VEF * 0.002 = 10 USD
        self.assertAlmostEqual(lead.expected_revenue_foreign, 200.0, places=2)
        self.assertAlmostEqual(lead.recurring_revenue_foreign, 10.0, places=2)

    def test_02_ignores_leads_with_no_historical_amount(self):
        lead = self.env["crm.lead"].create({
            "name": "Oportunidad ya migrada",
            "company_id": self.company.id,
            "expected_revenue_foreign": 50.0,
        })
        hooks.post_init_hook(self.env)
        lead.invalidate_recordset()
        # No debe tocar un registro que ya tiene su monto en moneda comercial.
        self.assertEqual(lead.expected_revenue_foreign, 50.0)

    def test_03_backfills_crm_team_invoiced_target(self):
        team = self.env["crm.team"].create({
            "name": "Equipo histórico",
            "company_id": self.company.id,
        })
        self.env.cr.execute(
            "UPDATE crm_team SET invoiced_target = %s WHERE id = %s",
            (250000.0, team.id),
        )
        team.invalidate_recordset()

        hooks.post_init_hook(self.env)
        team.invalidate_recordset()

        # 250000 VEF * 0.002 = 500 USD
        self.assertAlmostEqual(team.invoiced_target_foreign, 500.0, places=2)

    def test_04_skips_records_without_foreign_currency_configured(self):
        # El constraint permanente de res.company (_check_foreign_currency_id_required)
        # rechaza cualquier create()/write() sin foreign_currency_id, así que
        # para simular una compañía en ese estado (el escenario que este test
        # cubre) hay que insertarla por SQL directo, sin pasar por el ORM.
        company_without_foreign_currency = self.env["res.company"].browse(
            self.env["res.company"].create({
                "name": "Test Company Sin Moneda Alterna",
                "currency_id": self.vef.id,
                "foreign_currency_id": self.usd.id,
            }).id
        )
        self.env.cr.execute(
            "UPDATE res_company SET foreign_currency_id = NULL WHERE id = %s",
            (company_without_foreign_currency.id,),
        )
        company_without_foreign_currency.invalidate_recordset()

        team = self.env["crm.team"].create({
            "name": "Equipo sin moneda alterna",
            "company_id": company_without_foreign_currency.id,
        })
        self.env.cr.execute(
            "UPDATE crm_team SET invoiced_target = %s WHERE id = %s",
            (100000.0, team.id),
        )
        team.invalidate_recordset()

        # No debe lanzar aunque la compañía no tenga moneda comercial
        # configurada; simplemente no hay a dónde convertir.
        hooks.post_init_hook(self.env)
        team.invalidate_recordset()
        self.assertEqual(team.invoiced_target_foreign, 0.0)
