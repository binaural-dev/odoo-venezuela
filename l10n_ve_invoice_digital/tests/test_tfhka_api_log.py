import logging
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "invoice_digital")
class TestTfhkaApiLog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.com",
                "token_auth_tfhka": "token_fake",
            }
        )
        self.client = self.env["tfhka.api.client"]
        self.log_model = self.env["tfhka.api.log"]

    def _last_log(self, endpoint):
        return self.log_model.search(
            [("endpoint", "=", endpoint)], limit=1, order="id desc"
        )

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------

    def test_sanitize_payload_redacts_sensitive_keys(self):
        payload = {"usuario": "user@test", "clave": "secret"}
        sanitized = self.log_model._sanitize_payload(payload)
        self.assertEqual(sanitized["usuario"], "user@test")
        self.assertEqual(sanitized["clave"], "***")

    def test_sanitize_payload_ignores_non_dict(self):
        self.assertIsNone(self.log_model._sanitize_payload(None))
        self.assertEqual(self.log_model._sanitize_payload("raw"), "raw")

    # ------------------------------------------------------------------
    # Payload HTML formatting
    # ------------------------------------------------------------------

    def test_payload_to_html_wraps_in_pre_and_escapes(self):
        rendered = self.log_model._payload_to_html('{"a": "<script>"}')
        self.assertTrue(rendered.startswith("<pre"))
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_payload_to_html_empty_returns_false(self):
        self.assertFalse(self.log_model._payload_to_html(False))
        self.assertFalse(self.log_model._payload_to_html(""))

    def test_payload_to_html_highlights_tokens(self):
        rendered = self.log_model._payload_to_html('{\n  "a": 1,\n  "b": true\n}')
        self.assertIn(
            '<span style="color:#a626a4;font-weight:600">&quot;a&quot;</span>',
            rendered,
        )
        self.assertIn('<span style="color:#0184bc">1</span>', rendered)
        self.assertIn(
            '<span style="color:#c18401;font-weight:600">true</span>', rendered
        )

    def test_compute_payload_html_from_stored_json(self):
        log = self.log_model.create(
            {
                "endpoint": "/UltimoDocumento",
                "company_id": self.company.id,
                "request_payload": '{\n  "a": 1\n}',
                "response_payload": '{\n  "ok": true\n}',
            }
        )
        self.assertIn("&quot;a&quot;", log.request_payload_html)
        self.assertIn(">1<", log.request_payload_html)
        self.assertIn("&quot;ok&quot;", log.response_payload_html)
        self.assertIn(">true<", log.response_payload_html)

    # ------------------------------------------------------------------
    # Logging from the client
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_request_creates_log_entry_on_success(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": "200", "numeroDocumento": 5}
        mock_post.return_value = resp

        self.client._request(
            self.company, "ultimo_documento", {"serie": "", "tipoDocumento": "01"}
        )

        log = self._last_log("/UltimoDocumento")
        self.assertTrue(log)
        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 200)
        self.assertIn('"numeroDocumento": 5', log.response_payload)

    @patch("requests.post")
    def test_request_ultimo_documento_no_existe_is_logged_as_success(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": "203", "validaciones": ["no existe"]}
        mock_post.return_value = resp

        result = self.client._request(
            self.company, "ultimo_documento", {"serie": "", "tipoDocumento": "01"}
        )

        self.assertEqual(result, 0)
        log = self._last_log("/UltimoDocumento")
        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 200)

    @patch("requests.post")
    def test_request_logs_business_error(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": "400", "mensaje": "Error en la petición"}
        mock_post.return_value = resp

        # Nota: no se usa `self.assertRaises` aqui a proposito. En Odoo,
        # `TransactionCase.assertRaises` envuelve el bloque en un savepoint
        # que se revierte automaticamente en cuanto la excepcion esperada
        # ocurre (ver `_assertRaises` en odoo/tests/common.py), lo que
        # deshace tambien el log creado *antes* del `raise UserError`. Se
        # captura la excepcion manualmente para poder verificar el log.
        raised = False
        try:
            self.client._request(self.company, "emision", {"documentoElectronico": {}})
        except UserError:
            raised = True
        self.assertTrue(raised, "Expected UserError was not raised")

        log = self._last_log("/Emision")
        self.assertTrue(log, "no log found for /Emision")
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 200)

    @patch("requests.post")
    def test_request_logs_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("down")

        # Ver nota en test_request_logs_business_error sobre por que no se
        # usa `self.assertRaises` aqui.
        raised = False
        try:
            self.client._request(self.company, "emision", {"documentoElectronico": {}})
        except UserError:
            raised = True
        self.assertTrue(raised, "Expected UserError was not raised")

        log = self._last_log("/Emision")
        self.assertTrue(log, "no log found for /Emision")
        self.assertFalse(log.success)
        self.assertFalse(log.status_code)

    @patch("requests.post")
    def test_request_logs_password_redacted(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": "200", "resultado": {}}
        mock_post.return_value = resp

        self.client._request(
            self.company, "emision", {"clave": "topsecret", "otro": "dato"}
        )

        log = self._last_log("/Emision")
        self.assertNotIn("topsecret", log.request_payload)
        self.assertIn("***", log.request_payload)

    @patch("requests.post")
    def test_request_logs_origin(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": "200", "resultado": {}}
        mock_post.return_value = resp
        partner = self.env["res.partner"].create({"name": "Origin Partner"})

        self.client._request(
            self.company, "emision", {"documentoElectronico": {}}, origin=partner
        )

        log = self._last_log("/Emision")
        self.assertEqual(log.res_model, "res.partner")
        self.assertEqual(log.res_id, partner.id)
        self.assertEqual(log.res_name, partner.display_name)

    @patch("requests.post")
    def test_request_401_retries_and_logs_both_attempts(self, mock_post):
        def side_effect(url, *args, **kwargs):
            resp = MagicMock()
            if "/Autenticacion" in url:
                resp.status_code = 200
                resp.json.return_value = {"codigo": 200, "token": "refreshed"}
                return resp
            if not hasattr(side_effect, "calls"):
                side_effect.calls = 0
            side_effect.calls += 1
            if side_effect.calls == 1:
                resp.status_code = 401
                resp.text = "Unauthorized"
            else:
                resp.status_code = 200
                resp.json.return_value = {"codigo": "200", "resultado": {}}
            return resp

        mock_post.side_effect = side_effect

        self.client._request(self.company, "emision", {"documentoElectronico": {}})

        logs = self.log_model.search([("endpoint", "=", "/Emision")], order="id asc")
        self.assertEqual(len(logs), 2)
        self.assertFalse(logs[0].success)
        self.assertEqual(logs[0].status_code, 401)
        self.assertTrue(logs[1].success)
        self.assertEqual(logs[1].status_code, 200)

    # ------------------------------------------------------------------
    # Token generation (Autenticacion) is also logged
    # ------------------------------------------------------------------

    @patch("requests.post")
    def test_generate_token_success_is_logged(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": 200, "mensaje": "OK", "token": "abc123"}
        mock_post.return_value = resp

        self.company.generate_token_tfhka()

        log = self._last_log("/Autenticacion")
        self.assertTrue(log, "no log found for /Autenticacion")
        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 200)
        self.assertNotIn("clave_prueba", log.request_payload)
        self.assertIn("***", log.request_payload)

    @patch("requests.post")
    def test_generate_token_invalid_credentials_is_logged(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": 403, "mensaje": "Usuario/Clave incorrectos"}
        mock_post.return_value = resp

        raised = False
        try:
            self.company.generate_token_tfhka()
        except UserError:
            raised = True
        self.assertTrue(raised, "Expected UserError was not raised")

        log = self._last_log("/Autenticacion")
        self.assertTrue(log, "no log found for /Autenticacion")
        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 200)

    @patch("requests.post")
    def test_generate_token_connection_error_is_logged(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("down")

        raised = False
        try:
            self.company.generate_token_tfhka()
        except UserError:
            raised = True
        self.assertTrue(raised, "Expected UserError was not raised")

        log = self._last_log("/Autenticacion")
        self.assertTrue(log, "no log found for /Autenticacion")
        self.assertFalse(log.success)
        self.assertFalse(log.status_code)

    @patch("requests.post")
    def test_generate_token_no_token_in_response_is_logged(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"codigo": 200, "mensaje": "OK"}
        mock_post.return_value = resp

        raised = False
        try:
            self.company.generate_token_tfhka()
        except UserError:
            raised = True
        self.assertTrue(raised, "Expected UserError was not raised")

        log = self._last_log("/Autenticacion")
        self.assertTrue(log, "no log found for /Autenticacion")
        self.assertFalse(log.success)

    # ------------------------------------------------------------------
    # action_open_origin
    # ------------------------------------------------------------------

    def test_action_open_origin_without_link_returns_false(self):
        log = self.log_model.create(
            {"endpoint": "/Emision", "company_id": self.company.id}
        )
        self.assertFalse(log.action_open_origin())

    def test_action_open_origin_returns_act_window(self):
        partner = self.env["res.partner"].create({"name": "Origin Partner"})
        log = self.log_model.create(
            {
                "endpoint": "/Emision",
                "company_id": self.company.id,
                "res_model": "res.partner",
                "res_id": partner.id,
            }
        )
        action = log.action_open_origin()
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], partner.id)

    # ------------------------------------------------------------------
    # cron_purge_old_logs
    # ------------------------------------------------------------------

    def test_cron_purge_old_logs_removes_only_old_records(self):
        old_log = self.log_model.create(
            {"endpoint": "/Emision", "company_id": self.company.id}
        )
        recent_log = self.log_model.create(
            {"endpoint": "/Emision", "company_id": self.company.id}
        )
        old_log.write({"request_date": fields.Datetime.now() - timedelta(days=100)})
        recent_log.write({"request_date": fields.Datetime.now()})

        self.log_model.cron_purge_old_logs()

        self.assertFalse(old_log.exists())
        self.assertTrue(recent_log.exists())
