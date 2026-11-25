import importlib.util
import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

AUTH_URL = "https://api.tfhka.com/Autenticacion"
EMISSION_URL = "https://api.tfhka.com/Emision"


def _response(status_code, data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = json.dumps(data)
    return resp


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "tfhka_token_reuse")
class TestTfhkaTokenReuse(TransactionCase):
    """Ticket 16683: reuse the TFHKA token while it's valid, refresh it shortly
    before it expires (not only after a 401), and never keep it in the API
    call log."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.com",
                "token_auth_tfhka": "token_vigente",
                "token_expiry_tfhka": fields.Datetime.now() + timedelta(hours=6),
            }
        )
        self.client = self.env["tfhka.api.client"]
        self.log_model = self.env["tfhka.api.log"]
        self.new_expiry = (fields.Datetime.now() + timedelta(hours=12)).replace(microsecond=0)

    def _fake_api(self, emission_status=200):
        """Fake TFHKA: /Autenticacion hands out ``token_nuevo``; /Emision
        answers ``emission_status`` (a list = one status per call)."""
        statuses = list(emission_status) if isinstance(emission_status, (list, tuple)) else None

        def _post(url, json=None, headers=None, timeout=None):
            if url == AUTH_URL:
                return _response(
                    200,
                    {
                        "codigo": 200,
                        "mensaje": "OK",
                        "token": "token_nuevo",
                        "expiracion": self.new_expiry.strftime("%Y-%m-%dT%H:%M:%S.1234567Z"),
                    },
                )
            status = statuses.pop(0) if statuses is not None else emission_status
            if status == 401:
                return _response(401, {"mensaje": "Unauthorized"})
            return _response(200, {"codigo": "200", "mensaje": "OK"})

        return _post

    def _called_urls(self, mock_post):
        return [call.args[0] for call in mock_post.call_args_list]

    # ------------------------------------------------------------------
    # Reuse / proactive refresh
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_valid_token_is_reused_without_authenticating(self, mock_post):
        mock_post.side_effect = self._fake_api()

        for _i in range(3):
            self.client.emit(self.company, {"documento": "x"})

        self.assertEqual(self._called_urls(mock_post), [EMISSION_URL] * 3)
        for call in mock_post.call_args_list:
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer token_vigente")

    @patch("requests.post")
    def test_token_about_to_expire_is_refreshed_before_the_call(self, mock_post):
        self.company.token_expiry_tfhka = fields.Datetime.now() + timedelta(minutes=10)
        mock_post.side_effect = self._fake_api()

        self.client.emit(self.company, {"documento": "x"})

        self.assertEqual(self._called_urls(mock_post), [AUTH_URL, EMISSION_URL])
        self.assertEqual(
            mock_post.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer token_nuevo"
        )
        self.assertEqual(self.company.token_auth_tfhka, "token_nuevo")
        self.assertEqual(self.company.token_expiry_tfhka, self.new_expiry)

    @patch("requests.post")
    def test_expired_token_is_refreshed_before_the_call(self, mock_post):
        self.company.token_expiry_tfhka = fields.Datetime.now() - timedelta(hours=1)
        mock_post.side_effect = self._fake_api()

        self.client.emit(self.company, {"documento": "x"})

        self.assertEqual(self._called_urls(mock_post), [AUTH_URL, EMISSION_URL])

    @patch("requests.post")
    def test_refreshed_token_is_reused_by_following_calls(self, mock_post):
        self.company.token_expiry_tfhka = fields.Datetime.now() + timedelta(minutes=10)
        mock_post.side_effect = self._fake_api()

        for _i in range(3):
            self.client.emit(self.company, {"documento": "x"})

        self.assertEqual(self._called_urls(mock_post), [AUTH_URL] + [EMISSION_URL] * 3)

    @patch("requests.post")
    def test_legacy_token_without_expiry_keeps_waiting_for_401(self, mock_post):
        # Token guardado antes de existir token_expiry_tfhka: no se fuerza
        # una autenticación inmediata tras actualizar el módulo.
        self.company.token_expiry_tfhka = False
        mock_post.side_effect = self._fake_api()

        self.client.emit(self.company, {"documento": "x"})

        self.assertEqual(self._called_urls(mock_post), [EMISSION_URL])

    @patch("requests.post")
    def test_401_still_refreshes_and_retries_once(self, mock_post):
        mock_post.side_effect = self._fake_api(emission_status=[401, 200])

        self.client.emit(self.company, {"documento": "x"})

        self.assertEqual(self._called_urls(mock_post), [EMISSION_URL, AUTH_URL, EMISSION_URL])
        self.assertEqual(self.company.token_auth_tfhka, "token_nuevo")
        self.assertEqual(self.company.token_expiry_tfhka, self.new_expiry)

    # ------------------------------------------------------------------
    # Expiry parsing
    # ------------------------------------------------------------------

    def test_parse_expiry_uses_api_value(self):
        future = (fields.Datetime.now() + timedelta(hours=12)).replace(microsecond=0)
        value = future.strftime("%Y-%m-%dT%H:%M:%S") + ".5534384Z"
        self.assertEqual(self.company._parse_tfhka_token_expiry(value), future)

    def test_parse_expiry_falls_back_to_12_hours(self):
        for value in (None, "", "no-es-fecha", "2020-01-01T00:00:00Z", 12345):
            before = fields.Datetime.now() + timedelta(hours=12) - timedelta(seconds=5)
            parsed = self.company._parse_tfhka_token_expiry(value)
            self.assertTrue(
                before <= parsed <= fields.Datetime.now() + timedelta(hours=12),
                f"unexpected fallback for {value!r}: {parsed}",
            )

    # ------------------------------------------------------------------
    # Token never stored in the API log
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_auth_log_masks_token(self, mock_post):
        mock_post.side_effect = self._fake_api()

        self.company.generate_token_tfhka()

        log = self.log_model.search([("endpoint", "=", "/Autenticacion")], limit=1, order="id desc")
        self.assertTrue(log)
        self.assertNotIn("token_nuevo", log.response_payload)
        self.assertNotIn("clave_prueba", log.request_payload)
        self.assertEqual(json.loads(log.response_payload)["token"], "***")
        # El resto de la respuesta sigue disponible para soporte.
        self.assertIn("expiracion", json.loads(log.response_payload))

    def test_migration_masks_token_in_existing_logs(self):
        log_with_token = self.log_model.create(
            {
                "company_id": self.company.id,
                "endpoint": "/Autenticacion",
                "response_payload": json.dumps({"codigo": 200, "token": "secreto", "expiracion": "x"}, indent=2),
                "success": True,
            }
        )
        log_not_json = self.log_model.create(
            {
                "company_id": self.company.id,
                "endpoint": "/Autenticacion",
                "response_payload": 'connection error "token" plain text',
                "success": False,
            }
        )
        log_other_endpoint = self.log_model.create(
            {
                "company_id": self.company.id,
                "endpoint": "/Emision",
                "response_payload": json.dumps({"token": "no-se-toca"}),
                "success": True,
            }
        )
        self.env.flush_all()

        path = os.path.join(
            get_module_path("l10n_ve_invoice_digital"),
            "migrations",
            "17.0.0.0.40",
            "post-tfhka_mask_token_in_api_log.py",
        )
        spec = importlib.util.spec_from_file_location("tfhka_mask_token_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, "17.0.0.0.39")
        self.env.invalidate_all()

        self.assertEqual(json.loads(log_with_token.response_payload)["token"], "***")
        self.assertEqual(json.loads(log_with_token.response_payload)["expiracion"], "x")
        self.assertEqual(log_not_json.response_payload, 'connection error "token" plain text')
        self.assertIn("no-se-toca", log_other_endpoint.response_payload)

    def test_neutralize_clears_token_expiry(self):
        sql_path = os.path.join(get_module_path("l10n_ve_invoice_digital"), "data", "neutralize.sql")
        with open(sql_path) as sql_file:
            self.assertIn("token_expiry_tfhka = NULL", sql_file.read())
