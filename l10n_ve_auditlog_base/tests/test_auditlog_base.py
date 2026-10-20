from unittest.mock import patch, MagicMock

from odoo.tests import TransactionCase, tagged
from odoo.addons.l10n_ve_auditlog_base.models import requests_monitor

@tagged("post_install", "-at_install", "l10n_ve_auditlog_base")
class TestAuditlogBaseModels(TransactionCase):
    """Verify extended model field definitions."""

    def test_auditlog_http_request_extends_model(self):
        model = self.env["auditlog.http.request"]
        self.assertTrue(hasattr(model, "is_outgoing"))
        self.assertTrue(hasattr(model, "http_method"))
        self.assertTrue(hasattr(model, "request_url"))
        self.assertTrue(hasattr(model, "response_status"))
        self.assertTrue(hasattr(model, "error_type"))
        self.assertTrue(hasattr(model, "error_message"))
        self.assertTrue(hasattr(model, "error_traceback"))
        self.assertTrue(hasattr(model, "request_body"))
        self.assertTrue(hasattr(model, "response_body"))
        self.assertTrue(hasattr(model, "response_headers"))

    def test_is_outgoing_default_false(self):
        record = self.env["auditlog.http.request"].create({"name": "test"})
        self.assertFalse(record.is_outgoing)

    def test_res_company_audit_fields(self):
        company = self.env.company
        self.assertIn("log_outgoing_requests", company._fields)
        self.assertIn("response_body_max_chars", company._fields)

    def test_res_company_defaults(self):
        company = self.env.company
        company.write({
            "log_outgoing_requests": "errors_only",
            "response_body_max_chars": 0,
        })
        self.assertEqual(company.log_outgoing_requests, "errors_only")
        self.assertEqual(company.response_body_max_chars, 0)

    def test_res_config_settings_related_fields(self):
        model = self.env["res.config.settings"]
        self.assertIn("log_outgoing_requests", model._fields)
        self.assertIn("response_body_max_chars", model._fields)


@tagged("post_install", "-at_install", "l10n_ve_auditlog_base")
class TestRequestsMonitor(TransactionCase):
    """Test the outgoing request monitoring system."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.write({
            "log_outgoing_requests": "errors_only",
            "response_body_max_chars": 0,
        })

    def _mock_request(self):
        mock_req = MagicMock()
        mock_req.env = self.env
        return mock_req

    # ==================== _should_log_all ====================

    def test_should_log_all_errors_only(self):
        
        self.company.log_outgoing_requests = "errors_only"
        with patch.object(requests_monitor, "request", self._mock_request()):
            self.assertFalse(requests_monitor._should_log_all())

    def test_should_log_all_all(self):
        
        self.company.log_outgoing_requests = "all"
        with patch.object(requests_monitor, "request", self._mock_request()):
            self.assertTrue(requests_monitor._should_log_all())

    def test_should_log_all_no_request(self):
        
        with patch.object(requests_monitor, "request", None):
            self.assertFalse(requests_monitor._should_log_all())

    def test_should_log_all_request_no_env(self):
        
        mock_req = MagicMock()
        mock_req.env = None
        with patch.object(requests_monitor, "request", mock_req):
            self.assertFalse(requests_monitor._should_log_all())

    def test_should_log_all_exception(self):
        
        mock_req = MagicMock()
        mock_req.env = MagicMock(spec=[])
        with patch.object(requests_monitor, "request", mock_req):
            self.assertFalse(requests_monitor._should_log_all())

    # ==================== _log_failure ====================

    def test_log_failure_no_request(self):
        
        exc = requests_monitor.requests_lib.exceptions.ConnectionError("no conn")
        with patch.object(requests_monitor, "request", None):
            requests_monitor._log_failure("GET", "http://test.com/early", exc, {})

    def test_log_failure_request_no_env(self):
        
        mock_req = MagicMock()
        mock_req.env = None
        exc = requests_monitor.requests_lib.exceptions.ConnectionError("no env")
        with patch.object(requests_monitor, "request", mock_req):
            requests_monitor._log_failure("GET", "http://test.com/noenv", exc, {})

    def test_log_failure_without_response(self):
        
        exc = requests_monitor.requests_lib.exceptions.Timeout("timed out")
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_failure(
                "GET", "http://test.com/norsep", exc, {"data": "hello"},
            )
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/norsep"),
        ], limit=1)
        self.assertTrue(log)
        self.assertTrue(log.is_outgoing)
        self.assertEqual(log.http_method, "GET")
        self.assertEqual(log.error_type, "Timeout")
        self.assertIn("timed out", log.error_message)
        self.assertFalse(log.response_status)
        self.assertFalse(log.response_body)
        self.assertEqual(log.request_body, "hello")

    def test_log_failure_with_response(self):
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 502
        mock_resp.text = "Bad Gateway"
        mock_resp.headers = {"Server": "nginx"}
        exc = requests_monitor.requests_lib.exceptions.HTTPError("502 Bad Gateway")
        exc.response = mock_resp
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_failure("POST", "http://test.com/withresp", exc, {})
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/withresp"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.response_status, 502)
        self.assertEqual(log.response_body, "Bad Gateway")
        self.assertIn("nginx", log.response_headers)

    def test_log_failure_max_chars_truncation(self):
        self.company.response_body_max_chars = 3
        
        exc = requests_monitor.requests_lib.exceptions.ConnectionError("err")
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_failure(
                "GET", "http://test.com/truncbody", exc, {"data": "abcdefgh"},
            )
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/truncbody"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.request_body, "abc")

    def test_log_failure_with_json_body(self):
        
        exc = requests_monitor.requests_lib.exceptions.ConnectionError("err")
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_failure(
                "POST", "http://test.com/jsonbody", exc, {"json": {"a": 1}},
            )
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/jsonbody"),
        ], limit=1)
        self.assertTrue(log)
        self.assertIn("a", log.request_body)

    def test_log_failure_without_body(self):
        
        exc = requests_monitor.requests_lib.exceptions.ConnectionError("err")
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_failure("GET", "http://test.com/nobody", exc, {})
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/nobody"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.request_body, "")

    def test_log_failure_with_response_max_chars(self):
        self.company.response_body_max_chars = 5
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Long Error Message Here"
        mock_resp.headers = {}
        exc = requests_monitor.requests_lib.exceptions.HTTPError("err")
        exc.response = mock_resp
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_failure("GET", "http://test.com/resptrunc", exc, {})
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/resptrunc"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.response_body, "Long ")

    def test_log_failure_exception_during_logging(self):
        
        exc = requests_monitor.requests_lib.exceptions.ConnectionError("err")
        AuditlogRequest = self.env["auditlog.http.request"]
        with patch.object(type(AuditlogRequest), "create", side_effect=Exception("boom")), \
             patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_failure("GET", "http://test.com/excpath", exc, {})

    # ==================== _log_success ====================

    def test_log_success_no_request(self):
        
        with patch.object(requests_monitor, "request", None):
            requests_monitor._log_success("GET", "http://test.com/sucearly", MagicMock(), {})

    def test_log_success_request_no_env(self):
        
        mock_req = MagicMock()
        mock_req.env = None
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        with patch.object(requests_monitor, "request", mock_req):
            requests_monitor._log_success("GET", "http://test.com/sucnoenv", mock_resp, {})

    def test_log_success_creates_record(self):
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {"Content-Type": "text/plain"}
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_success("GET", "http://test.com/success1", mock_resp, {})
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/success1"),
        ], limit=1)
        self.assertTrue(log)
        self.assertTrue(log.is_outgoing)
        self.assertEqual(log.response_status, 200)
        self.assertEqual(log.response_body, "OK")

    def test_log_success_with_body(self):
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {}
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_success(
                "POST", "http://test.com/sucbody", mock_resp, {"data": "sent"},
            )
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/sucbody"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.request_body, "sent")

    def test_log_success_json_body(self):
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {}
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_success(
                "POST", "http://test.com/sucjson", mock_resp, {"json": {"b": 2}},
            )
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/sucjson"),
        ], limit=1)
        self.assertTrue(log)
        self.assertIn("b", log.request_body)

    def test_log_success_max_chars_request(self):
        self.company.response_body_max_chars = 2
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {}
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_success(
                "GET", "http://test.com/sucrtrunc", mock_resp, {"data": "abcdefgh"},
            )
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/sucrtrunc"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.request_body, "ab")

    def test_log_success_max_chars_response(self):
        self.company.response_body_max_chars = 5
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "Hello World"
        mock_resp.headers = {}
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_success("GET", "http://test.com/sucrtrunc2", mock_resp, {})
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/sucrtrunc2"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.response_body, "Hello")

    def test_log_success_no_body(self):
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 204
        mock_resp.text = ""
        mock_resp.headers = {}
        with patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_success("DELETE", "http://test.com/sucnobody", mock_resp, {})
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/sucnobody"),
        ], limit=1)
        self.assertTrue(log)
        self.assertEqual(log.response_body, "")

    def test_log_success_exception_during_logging(self):
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {}
        AuditlogRequest = self.env["auditlog.http.request"]
        with patch.object(type(AuditlogRequest), "create", side_effect=Exception("boom")), \
             patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._log_success("GET", "http://test.com/sucexclog", mock_resp, {})

    # ==================== _patched_request ====================

    def test_patched_request_success_not_logged(self):
        
        self.company.log_outgoing_requests = "errors_only"
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        with patch.object(requests_monitor, "_original_request", return_value=mock_resp), \
             patch.object(requests_monitor, "request", self._mock_request()):
            result = requests_monitor._patched_request(None, "GET", "http://test.com/p1")
            self.assertIs(result, mock_resp)

    def test_patched_request_success_logged(self):
        
        self.company.log_outgoing_requests = "all"
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {}
        with patch.object(requests_monitor, "_original_request", return_value=mock_resp), \
             patch.object(requests_monitor, "request", self._mock_request()):
            result = requests_monitor._patched_request(None, "GET", "http://test.com/p2")
            self.assertIs(result, mock_resp)
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/p2"),
        ], limit=1)
        self.assertTrue(log)

    def test_patched_request_failure(self):
        
        mock_req = MagicMock()
        mock_req.env = self.env
        exc = requests_monitor.requests_lib.exceptions.ConnectionError("fail")
        raised = False
        with patch.object(requests_monitor, "_original_request", side_effect=exc), \
             patch.object(requests_monitor, "request", mock_req):
            try:
                requests_monitor._patched_request(None, "GET", "http://test.com/pfail")
            except requests_monitor.requests_lib.exceptions.ConnectionError:
                raised = True
        self.assertTrue(raised)
        log = self.env["auditlog.http.request"].search([
            ("request_url", "=", "http://test.com/pfail"),
        ], limit=1)
        self.assertTrue(log)

    def test_patched_request_passes_kwargs(self):
        
        mock_resp = MagicMock(spec=requests_monitor.requests_lib.Response)
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.headers = {}
        self.company.log_outgoing_requests = "all"
        with patch.object(requests_monitor, "_original_request", return_value=mock_resp) as mock_orig, \
             patch.object(requests_monitor, "request", self._mock_request()):
            requests_monitor._patched_request(
                None, "POST", "http://test.com/pk", data="payload",
            )
            mock_orig.assert_called_once_with(None, "POST", "http://test.com/pk", data="payload")

    # ==================== Monkey-patching ====================

    def test_requests_session_request_is_patched(self):
        self.assertIs(
            requests_monitor.requests_lib.Session.request,
            requests_monitor._patched_request,
        )
