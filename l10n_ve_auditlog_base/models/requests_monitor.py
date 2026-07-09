import logging
import traceback

import requests as requests_lib

from odoo.http import request

_logger = logging.getLogger(__name__)


def _log_failure(method, url, exception, kwargs):
    try:
        if not request or not request.env:
            _logger.info(
                "No Odoo request context, skipping audit log for failed outgoing "
                "request: %s %s - %s",
                method, url, exception,
            )
            return
        response_status = None
        response = getattr(exception, "response", None)
        if response is not None:
            response_status = response.status_code
        body = kwargs.get("data") or kwargs.get("json") or ""
        request.env["auditlog.http.request"].create({
            "is_outgoing": True,
            "http_method": method.upper(),
            "request_url": url,
            "response_status": response_status,
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "error_traceback": traceback.format_exc(),
            "request_body": str(body)[:2000],
            "user_id": request.env.uid,
            "name": url,
        })
    except Exception as log_error:
        _logger.warning("Failed to log outgoing request failure: %s", log_error)


def _log_success(method, url, response, kwargs):
    try:
        if not request or not request.env:
            return
        body = kwargs.get("data") or kwargs.get("json") or ""
        request.env["auditlog.http.request"].sudo().create({
            "is_outgoing": True,
            "http_method": method.upper(),
            "request_url": url,
            "response_status": response.status_code,
            "request_body": str(body)[:2000],
            "user_id": request.env.uid,
            "name": url,
        })
    except Exception as log_error:
        _logger.warning("Failed to log outgoing request success: %s", log_error)


def _should_log_all():
    try:
        if request and request.env:
            return request.env.company.log_outgoing_requests == "all"
    except Exception:
        pass
    return False


_original_request = requests_lib.Session.request


def _patched_request(self, method, url, **kwargs):
    try:
        response = _original_request(self, method, url, **kwargs)
    except requests_lib.exceptions.RequestException as exc:
        _logger.error(
            "Outgoing request failed: %s %s",
            method.upper(), url, exc_info=True,
        )
        _log_failure(method, url, exc, kwargs)
        raise
    else:
        if _should_log_all():
            _log_success(method, url, response, kwargs)
        return response


requests_lib.Session.request = _patched_request
