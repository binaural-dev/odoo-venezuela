from odoo import fields, models


class AuditlogHTTPRequest(models.Model):
    _inherit = "auditlog.http.request"

    is_outgoing = fields.Boolean(
        "Is Outgoing Request",
        default=False,
        help="If True, this record corresponds to an outgoing external HTTP request "
        "(e.g. API call to Tesote, Megasoft, BCV, etc.) rather than an incoming Odoo request.",
    )
    http_method = fields.Char(
        "HTTP Method",
        help="HTTP method used for the outgoing request: GET, POST, PUT, DELETE, etc.",
    )
    request_url = fields.Text(
        "Request URL",
        help="Full URL of the external endpoint that was called.",
    )
    response_status = fields.Integer(
        "Response Status",
        help="HTTP status code returned by the external server, if a response was "
        "received before the error occurred (e.g. 500, 502, 503).",
    )
    error_type = fields.Char(
        "Error Type",
        help="Python exception class name: ConnectionError, Timeout, HTTPError, etc.",
    )
    error_message = fields.Text(
        "Error Message",
        help="Exception message with details about why the request failed.",
    )
    error_traceback = fields.Text(
        "Error Traceback",
        help="Full Python traceback at the moment the failure occurred, useful for debugging.",
    )
    request_body = fields.Text(
        "Request Body",
        help="Payload sent in the request body (truncated to 2000 characters).",
    )
