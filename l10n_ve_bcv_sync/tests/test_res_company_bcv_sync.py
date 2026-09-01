from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_bcv_sync", "res_company")
class TestBcvSyncResCompany(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.usd = cls.env.ref("base.USD")
        cls.vef = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VEF")], limit=1)
        )
        cls.eur = cls.env.ref("base.EUR")
        cls.vef.sudo().active = True
        cls.usd.sudo().active = True
        cls.company.sudo().currency_id = cls.vef
        cls.Rate = cls.env["res.currency.rate"].sudo()

    def setUp(self):
        super().setUp()
        # Each test starts with no prior USD rates, so it doesn't collide
        # with the unique(name, currency_id, company_id) constraint.
        self.Rate.search(
            [("currency_id", "=", self.usd.id), ("company_id", "=", self.company.id)]
        ).unlink()
        self.company.can_update_habil_days = True
        self.company.currency_id = self.vef

    def test_accepts_rate_for_today(self):
        today = fields.Date.context_today(self.company)
        tasas = [{"moneda": "USD", "valor": "791.66670000", "fecha_valor": str(today)}]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], ["USD"])
        self.assertEqual(summary["skipped"], [])
        rate = self.Rate.search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", today),
            ]
        )
        self.assertEqual(len(rate), 1)
        self.assertAlmostEqual(rate.inverse_company_rate, 791.6667, places=3)

    def test_rejects_future_rate_when_habil_days_disabled(self):
        self.company.can_update_habil_days = False
        today = fields.Date.context_today(self.company)
        future_date = today + timedelta(days=2)
        tasas = [{"moneda": "USD", "valor": "800.0", "fecha_valor": str(future_date)}]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], [])
        self.assertEqual(summary["skipped"], ["USD"])
        self.assertFalse(
            self.Rate.search(
                [
                    ("currency_id", "=", self.usd.id),
                    ("company_id", "=", self.company.id),
                    ("name", "=", future_date),
                ]
            )
        )

    def test_accepts_future_rate_when_habil_days_enabled(self):
        self.company.can_update_habil_days = True
        today = fields.Date.context_today(self.company)
        future_date = today + timedelta(days=2)
        tasas = [{"moneda": "USD", "valor": "800.0", "fecha_valor": str(future_date)}]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], ["USD"])
        rate = self.Rate.search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", future_date),
            ]
        )
        self.assertEqual(len(rate), 1)
        self.assertAlmostEqual(rate.inverse_company_rate, 800.0, places=3)

    def test_unknown_currency_does_not_abort_the_rest_of_the_payload(self):
        today = fields.Date.context_today(self.company)
        tasas = [
            {"moneda": "XYZ", "valor": "1.0", "fecha_valor": str(today)},
            {"moneda": "USD", "valor": "791.6667", "fecha_valor": str(today)},
        ]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["skipped"], ["XYZ"])
        self.assertEqual(summary["applied"], ["USD"])

    def test_invalid_valor_is_skipped(self):
        today = fields.Date.context_today(self.company)
        tasas = [{"moneda": "USD", "valor": "not-a-number", "fecha_valor": str(today)}]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], [])
        self.assertEqual(summary["skipped"], ["USD"])

    def test_invalid_fecha_valor_is_skipped(self):
        tasas = [{"moneda": "USD", "valor": "791.6667", "fecha_valor": "not-a-date"}]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], [])
        self.assertEqual(summary["skipped"], ["USD"])

    def test_non_vef_company_currency_skips_everything(self):
        self.company.currency_id = self.usd
        today = fields.Date.context_today(self.company)
        tasas = [
            {"moneda": "USD", "valor": "791.6667", "fecha_valor": str(today)},
            {"moneda": "EUR", "valor": "921.88", "fecha_valor": str(today)},
        ]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], [])
        self.assertEqual(sorted(summary["skipped"]), ["EUR", "USD"])

    def test_idempotent_upsert_does_not_duplicate_the_rate(self):
        today = fields.Date.context_today(self.company)
        tasas = [{"moneda": "USD", "valor": "791.6667", "fecha_valor": str(today)}]

        self.company._bcv_sync_process_tasas(tasas)
        self.company._bcv_sync_process_tasas(tasas)

        rates = self.Rate.search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", today),
            ]
        )
        self.assertEqual(len(rates), 1)

    def test_todays_rate_is_not_overwritten_once_set(self):
        # Accounting stability: once today's rate is set, a later run the
        # same day must not silently change it under transactions already
        # posted -- unlike advance (future) dates, which do keep refreshing.
        today = fields.Date.context_today(self.company)
        self.company._bcv_sync_process_tasas(
            [{"moneda": "USD", "valor": "700.0", "fecha_valor": str(today)}]
        )
        summary = self.company._bcv_sync_process_tasas(
            [{"moneda": "USD", "valor": "791.6667", "fecha_valor": str(today)}]
        )

        self.assertEqual(summary["applied"], [])
        self.assertEqual(summary["skipped"], ["USD"])
        rate = self.Rate.search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", today),
            ]
        )
        self.assertEqual(len(rate), 1)
        self.assertAlmostEqual(rate.inverse_company_rate, 700.0, places=3)

    def test_future_rate_keeps_refreshing_on_replay(self):
        # The "don't overwrite" rule is scoped to today only -- an advance
        # rate for a future date keeps getting refreshed on every run
        # until it actually becomes today, in case BCV revises it.
        self.company.can_update_habil_days = True
        today = fields.Date.context_today(self.company)
        future_date = today + timedelta(days=2)
        self.company._bcv_sync_process_tasas(
            [{"moneda": "USD", "valor": "800.0", "fecha_valor": str(future_date)}]
        )
        summary = self.company._bcv_sync_process_tasas(
            [{"moneda": "USD", "valor": "810.0", "fecha_valor": str(future_date)}]
        )

        self.assertEqual(summary["applied"], ["USD"])
        rate = self.Rate.search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", future_date),
            ]
        )
        self.assertEqual(len(rate), 1)
        self.assertAlmostEqual(rate.inverse_company_rate, 810.0, places=3)

    def test_inactive_currency_is_skipped_even_if_known_to_odoo(self):
        # Unlike an unrecognized code (e.g. "XYZ"), EUR is a real Odoo
        # currency -- but if this company never activated it, BCV Sync
        # must not start tracking it just because it showed up in a
        # payload.
        self.eur.sudo().active = False
        today = fields.Date.context_today(self.company)
        tasas = [
            {"moneda": "EUR", "valor": "921.88", "fecha_valor": str(today)},
            {"moneda": "USD", "valor": "791.6667", "fecha_valor": str(today)},
        ]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["skipped"], ["EUR"])
        self.assertEqual(summary["applied"], ["USD"])
        self.assertFalse(
            self.Rate.search(
                [
                    ("currency_id", "=", self.eur.id),
                    ("company_id", "=", self.company.id),
                    ("name", "=", today),
                ]
            )
        )

    def test_past_fecha_valor_is_rejected_when_habil_days_enabled(self):
        self.company.can_update_habil_days = True
        today = fields.Date.context_today(self.company)
        past_date = today - timedelta(days=1)
        tasas = [{"moneda": "USD", "valor": "791.6667", "fecha_valor": str(past_date)}]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], [])
        self.assertEqual(summary["skipped"], ["USD"])
        self.assertFalse(
            self.Rate.search(
                [
                    ("currency_id", "=", self.usd.id),
                    ("company_id", "=", self.company.id),
                    ("name", "=", past_date),
                ]
            )
        )

    def test_past_fecha_valor_is_rejected_when_habil_days_disabled(self):
        # This module never backdates a rate, regardless of the flag --
        # unlike l10n_ve_currency_rate_live's own _is_valid_rate_date,
        # which this module deliberately does not reuse for this branch.
        self.company.can_update_habil_days = False
        today = fields.Date.context_today(self.company)
        past_date = today - timedelta(days=1)
        tasas = [{"moneda": "USD", "valor": "791.6667", "fecha_valor": str(past_date)}]

        summary = self.company._bcv_sync_process_tasas(tasas)

        self.assertEqual(summary["applied"], [])
        self.assertEqual(summary["skipped"], ["USD"])
        self.assertFalse(
            self.Rate.search(
                [
                    ("currency_id", "=", self.usd.id),
                    ("company_id", "=", self.company.id),
                    ("name", "=", past_date),
                ]
            )
        )

    def test_get_company_by_token_matches_configured_key(self):
        self.company.bcv_sync_api_key = "s3cr3t-token"

        found = self.env["res.company"]._bcv_sync_get_company_by_token("s3cr3t-token")
        not_found = self.env["res.company"]._bcv_sync_get_company_by_token("wrong")
        empty = self.env["res.company"]._bcv_sync_get_company_by_token("")

        self.assertEqual(found, self.company)
        self.assertFalse(not_found)
        self.assertFalse(empty)
