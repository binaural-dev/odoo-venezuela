import html
import logging
import re

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {"password", "clave", "authorization"}
PURGE_AFTER_MONTHS = 3

# Tokenizes a pretty-printed JSON string for syntax highlighting. Order
# matters: a quoted string immediately followed by ":" is a key, otherwise
# it is a string value.
JSON_TOKEN_RE = re.compile(
    r'(?P<key>"(?:\\.|[^"\\])*"(?=\s*:))'
    r'|(?P<string>"(?:\\.|[^"\\])*")'
    r"|(?P<bool>true|false)"
    r"|(?P<null>null)"
    r"|(?P<number>-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
)

JSON_TOKEN_STYLES = {
    "key": "color:#a626a4;font-weight:600",
    "string": "color:#50a14f",
    "bool": "color:#c18401;font-weight:600",
    "null": "color:#986801;font-style:italic",
    "number": "color:#0184bc",
}


class TfhkaApiLog(models.Model):
    _name = "tfhka.api.log"
    _description = "TFHKA API Call Log"
    _order = "request_date desc, id desc"

    endpoint = fields.Char(required=True, index=True)
    http_method = fields.Char(string="HTTP Method")
    company_id = fields.Many2one("res.company", string="Company", required=True)
    request_date = fields.Datetime(
        string="Date", required=True, default=fields.Datetime.now, index=True
    )
    request_payload = fields.Text(string="Request")
    response_payload = fields.Text(string="Response")
    request_payload_html = fields.Html(
        string="Request", compute="_compute_payload_html", sanitize=False
    )
    response_payload_html = fields.Html(
        string="Response", compute="_compute_payload_html", sanitize=False
    )
    status_code = fields.Integer(string="HTTP Status", group_operator=None)
    success = fields.Boolean()

    res_model = fields.Char(string="Origin Model")
    res_id = fields.Integer(string="Origin Record ID")
    res_name = fields.Char(string="Origin Document")

    @api.depends("request_payload", "response_payload")
    def _compute_payload_html(self):
        for log in self:
            log.request_payload_html = self._payload_to_html(log.request_payload)
            log.response_payload_html = self._payload_to_html(log.response_payload)

    @api.model
    def _payload_to_html(self, value):
        """Render a pretty-printed JSON string as syntax-highlighted HTML.

        Keeps the original indentation/line breaks (``white-space: pre-wrap``
        still wraps long lines so nothing needs horizontal scrolling) while
        coloring keys, strings, numbers, booleans and null like a code editor.
        Every token is escaped before being inserted, and the untouched
        separators (braces, commas, whitespace) can't contain HTML-special
        characters in valid JSON, so this is safe against injection.
        """
        if not value:
            return False

        def _highlight(match):
            kind = match.lastgroup
            text = html.escape(match.group(0))
            return f'<span style="{JSON_TOKEN_STYLES[kind]}">{text}</span>'

        highlighted = JSON_TOKEN_RE.sub(_highlight, value)
        return Markup(
            '<pre style="white-space:pre-wrap;word-break:break-word;'
            'font-family:monospace;font-size:12px;margin:0;">'
        ) + Markup(highlighted) + Markup("</pre>")

    @api.model
    def _sanitize_payload(self, payload):
        """Redact sensitive keys (e.g. the login password) before persisting."""
        if not isinstance(payload, dict):
            return payload
        sanitized = {}
        for key, value in payload.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                sanitized[key] = "***"
            else:
                sanitized[key] = value
        return sanitized

    def action_open_origin(self):
        self.ensure_one()
        if not (self.res_model and self.res_id):
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    def cron_purge_old_logs(self):
        threshold = fields.Datetime.now() - relativedelta(months=PURGE_AFTER_MONTHS)
        old_logs = self.sudo().search([("request_date", "<", threshold)])
        count = len(old_logs)
        old_logs.unlink()
        if count:
            _logger.info(
                "TFHKA: purged %s API log record(s) older than %s months",
                count,
                PURGE_AFTER_MONTHS,
            )
