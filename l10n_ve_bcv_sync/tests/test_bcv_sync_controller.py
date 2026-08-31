import json

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_bcv_sync")
class TestBcvSyncController(HttpCase):
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
        cls.vef.sudo().active = True
        cls.usd.sudo().active = True
        cls.company.sudo().write(
            {
                "currency_id": cls.vef.id,
                "can_update_habil_days": True,
                "bcv_sync_api_key": "test-api-key",
            }
        )

    def setUp(self):
        super().setUp()
        self.env["res.currency.rate"].sudo().search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
            ]
        ).unlink()

    def _post(self, body, token="test-api-key"):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return self.url_open(
            "/api/tasas-bcv",
            data=json.dumps(body) if body is not None else None,
            headers=headers,
        )

    def test_missing_authorization_header_returns_401(self):
        response = self._post({"tasas": []}, token=None)

        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json().get("ok") is False)

    def test_invalid_token_returns_401(self):
        response = self._post({"tasas": []}, token="not-the-right-key")

        self.assertEqual(response.status_code, 401)

    def test_malformed_payload_without_tasas_returns_400(self):
        response = self._post({"fecha": fields.Datetime.now().isoformat()})

        self.assertEqual(response.status_code, 400)

    def test_valid_payload_returns_200_and_persists_the_rate(self):
        today = fields.Date.context_today(self.company)
        response = self._post(
            {
                "fecha": fields.Datetime.now().isoformat(),
                "tasas": [
                    {"moneda": "USD", "valor": "791.66670000", "fecha_valor": str(today)}
                ],
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["applied"], ["USD"])

        rate = self.env["res.currency.rate"].sudo().search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", today),
            ]
        )
        self.assertEqual(len(rate), 1)
        self.assertAlmostEqual(rate.inverse_company_rate, 791.6667, places=3)

    def test_duplicate_request_is_idempotent(self):
        today = fields.Date.context_today(self.company)
        payload = {
            "fecha": fields.Datetime.now().isoformat(),
            "tasas": [
                {"moneda": "USD", "valor": "791.66670000", "fecha_valor": str(today)}
            ],
        }

        first = self._post(payload)
        second = self._post(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        rate = self.env["res.currency.rate"].sudo().search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.company.id),
                ("name", "=", today),
            ]
        )
        self.assertEqual(len(rate), 1)

    def test_unknown_currency_is_ignored_without_failing_the_request(self):
        today = fields.Date.context_today(self.company)
        response = self._post(
            {
                "tasas": [
                    {"moneda": "XYZ", "valor": "1.0", "fecha_valor": str(today)},
                    {
                        "moneda": "USD",
                        "valor": "791.6667",
                        "fecha_valor": str(today),
                    },
                ]
            }
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["applied"], ["USD"])
        self.assertEqual(data["skipped"], ["XYZ"])
