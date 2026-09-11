from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

CLIENT_REQUESTS_PATH = (
    "odoo.addons.l10n_ve_invoice_digital.services.tfhka_client.requests.post"
)


def _response(status_code=200, json_data=None):
    response = MagicMock()
    response.status_code = status_code
    if json_data is None:
        response.json.side_effect = ValueError("no json")
        response.text = "not json"
    else:
        response.json.return_value = json_data
    return response


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital")
class TestTfhkaApiLog(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "username_tfhka": "usuario_prueba",
                "password_tfhka": "clave_prueba",
                "url_tfhka": "https://api.tfhka.test",
                "token_auth_tfhka": "token-123",
            }
        )
        self.client = self.env["tfhka.api.client"]
        self.log_model = self.env["tfhka.api.log"]

    def _last_log(self, domain):
        """Read the log's field values through a brand-new cursor.

        ``_log_call`` persists via its own isolated cursor so the entry
        survives even if the caller raises right after (see
        ``tfhka_client.py``). Odoo cursors run at REPEATABLE READ, so the
        test's own cursor took its snapshot before that isolated cursor
        committed and will never see the row; a fresh cursor opened here
        takes its snapshot afterwards and does. Returns a plain dict (or
        None) since the underlying recordset can't outlive this cursor.
        """
        with self.registry.cursor() as cr:
            log = self.env(cr=cr)["tfhka.api.log"].search(
                domain, limit=1, order="id desc"
            )
            if not log:
                return None
            return {
                "success": log.success,
                "status_code": log.status_code,
                "response_payload": log.response_payload,
                "request_payload": log.request_payload,
                "res_model": log.res_model,
                "res_id": log.res_id,
                "res_name": log.res_name,
            }

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------

    def test_sanitize_payload_redacts_password_and_clave(self):
        payload = {"usuario": "user@test", "clave": "secret"}
        sanitized = self.log_model._sanitize_payload(payload)
        self.assertEqual(sanitized["usuario"], "user@test")
        self.assertEqual(sanitized["clave"], "***")

    def test_sanitize_payload_ignores_non_dict(self):
        self.assertEqual(self.log_model._sanitize_payload(None), None)
        self.assertEqual(self.log_model._sanitize_payload("raw"), "raw")

    def test_sanitize_payload_redacts_token(self):
        payload = {"token": "secret-token", "codigo": 200}
        sanitized = self.log_model._sanitize_payload(payload)
        self.assertEqual(sanitized["token"], "***")
        self.assertEqual(sanitized["codigo"], 200)

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

    def test_payload_to_html_escapes_non_json_payload(self):
        """A raw, non-JSON body (e.g. an HTML error page from a proxy in
        front of TFHKA) must come out fully escaped, not partially matched
        by the JSON token regex."""
        rendered = self.log_model._payload_to_html("<script>alert(1)</script>")
        self.assertTrue(rendered.startswith("<pre"))
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)

    def test_payload_to_html_highlights_tokens(self):
        rendered = self.log_model._payload_to_html('{\n  "a": 1,\n  "b": true\n}')
        self.assertIn(
            '<span style="color:#a626a4;font-weight:600">&quot;a&quot;</span>', rendered
        )
        self.assertIn('<span style="color:#0184bc">1</span>', rendered)
        self.assertIn('<span style="color:#c18401;font-weight:600">true</span>', rendered)

    def test_compute_payload_html_from_stored_json(self):
        log = self.log_model.create(
            {
                "endpoint": "/Emision",
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

    def test_request_creates_log_entry_on_success(self):
        with patch(
            CLIENT_REQUESTS_PATH,
            return_value=_response(json_data={"codigo": "200", "resultado": {}}),
        ):
            self.client.emit(self.company, {"foo": "bar"})
        log = self._last_log([("endpoint", "=", "/Emision")])
        self.assertTrue(log)
        self.assertTrue(log["success"])
        self.assertEqual(log["status_code"], 200)
        self.assertIn('"codigo"', log["response_payload"])

    def test_request_logs_sensitive_key_redacted(self):
        with patch(
            CLIENT_REQUESTS_PATH,
            return_value=_response(json_data={"codigo": "200"}),
        ):
            self.client._request(
                self.company, "emision", {"usuario": "u", "clave": "topsecret"}
            )
        log = self._last_log([("endpoint", "=", "/Emision")])
        self.assertTrue(log)
        self.assertNotIn("topsecret", log["request_payload"])
        self.assertIn("***", log["request_payload"])

    def test_request_logs_connection_error(self):
        with patch(
            CLIENT_REQUESTS_PATH,
            side_effect=requests.exceptions.RequestException("down"),
        ):
            with self.assertRaises(UserError):
                self.client.emit(self.company, {"foo": "bar"})
        log = self._last_log([("endpoint", "=", "/Emision")])
        self.assertTrue(log)
        self.assertFalse(log["success"])
        self.assertFalse(log["status_code"])

    def test_request_logs_origin(self):
        with patch(
            CLIENT_REQUESTS_PATH,
            return_value=_response(json_data={"codigo": "200"}),
        ):
            self.client.emit(self.company, {"foo": "bar"}, origin=self.company)
        log = self._last_log([("endpoint", "=", "/Emision")])
        self.assertTrue(log)
        self.assertEqual(log["res_model"], "res.company")
        self.assertEqual(log["res_id"], self.company.id)
        self.assertEqual(log["res_name"], self.company.display_name)

    def test_request_survives_a_usererror_raised_after_logging(self):
        """A call that ends in a UserError (e.g. a business error TFHKA
        returned via ``codigo``) still leaves a log entry behind, not just
        a network-level failure."""
        with patch(
            CLIENT_REQUESTS_PATH,
            return_value=_response(
                json_data={"codigo": "500", "mensaje": "boom", "validaciones": []}
            ),
        ):
            with self.assertRaises(UserError):
                self.client.emit(self.company, {"foo": "bar"})
        log = self._last_log([("endpoint", "=", "/Emision")])
        self.assertTrue(log)
        self.assertFalse(log["success"])

    def test_generate_token_logs_the_authentication_call(self):
        with patch(
            "requests.post",
            return_value=_response(
                json_data={"codigo": 200, "mensaje": "OK", "token": "new-token"}
            ),
        ):
            self.company.generate_token_tfhka()
        log = self._last_log([("endpoint", "=", "/Autenticacion")])
        self.assertTrue(log)
        self.assertTrue(log["success"])
        self.assertNotIn("clave_prueba", log["request_payload"])
        self.assertIn("***", log["request_payload"])
        self.assertNotIn("new-token", log["response_payload"])
        self.assertIn("***", log["response_payload"])
        self.assertEqual(self.company.token_auth_tfhka, "new-token")

    def test_request_logs_token_redacted_in_response(self):
        with patch(
            CLIENT_REQUESTS_PATH,
            return_value=_response(
                json_data={"codigo": "200", "token": "leaked-token"}
            ),
        ):
            self.client.emit(self.company, {"foo": "bar"})
        log = self._last_log([("endpoint", "=", "/Emision")])
        self.assertTrue(log)
        self.assertNotIn("leaked-token", log["response_payload"])
        self.assertIn("***", log["response_payload"])

    # ------------------------------------------------------------------
    # action_open_origin
    # ------------------------------------------------------------------

    def test_action_open_origin_without_link_returns_false(self):
        log = self.log_model.create(
            {"endpoint": "/Emision", "company_id": self.company.id}
        )
        self.assertFalse(log.action_open_origin())

    def test_action_open_origin_returns_act_window(self):
        log = self.log_model.create(
            {
                "endpoint": "/Emision",
                "company_id": self.company.id,
                "res_model": "res.company",
                "res_id": self.company.id,
            }
        )
        action = log.action_open_origin()
        self.assertEqual(action["res_model"], "res.company")
        self.assertEqual(action["res_id"], self.company.id)

    # ------------------------------------------------------------------
    # Multi-company access
    # ------------------------------------------------------------------

    def test_logs_are_restricted_by_company(self):
        other_company = self.env["res.company"].create({"name": "Other TFHKA Co"})
        own_log = self.log_model.create(
            {"endpoint": "/Emision", "company_id": self.company.id}
        )
        other_log = self.log_model.create(
            {"endpoint": "/Emision", "company_id": other_company.id}
        )

        restricted_user = self.env["res.users"].create(
            {
                "name": "TFHKA Restricted User",
                "login": "tfhka_restricted_user",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(
                                "l10n_ve_invoice_digital.group_l10n_ve_invoice_digital_admin"
                            ).id,
                        ],
                    )
                ],
                "company_ids": [(6, 0, [self.company.id])],
                "company_id": self.company.id,
            }
        )

        visible_logs = self.log_model.with_user(restricted_user).search(
            [("id", "in", (own_log + other_log).ids)]
        )
        self.assertEqual(visible_logs, own_log)

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
