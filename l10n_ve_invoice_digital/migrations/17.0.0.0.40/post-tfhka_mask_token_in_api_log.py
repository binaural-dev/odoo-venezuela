import json
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Until now the /Autenticacion response was stored as-is in
    ``tfhka.api.log.response_payload``, Bearer token included, and that log
    is readable from the UI (ticket 16683). New entries are masked when
    written (``token`` is now one of ``SENSITIVE_KEYS``); this masks the
    ones already stored.

    Done in Python rather than with ``::jsonb`` in SQL so a single entry that
    isn't valid JSON (e.g. a connection error stored as plain text) is just
    skipped instead of aborting the whole upgrade.
    """
    if not version:
        return

    cr.execute(
        """
        SELECT id, response_payload
          FROM tfhka_api_log
         WHERE endpoint = '/Autenticacion'
           AND response_payload LIKE '%%"token"%%'
        """
    )
    masked = 0
    for log_id, response_payload in cr.fetchall():
        try:
            data = json.loads(response_payload)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or "token" not in data:
            continue
        data["token"] = "***"
        cr.execute(
            "UPDATE tfhka_api_log SET response_payload = %s WHERE id = %s",
            (json.dumps(data, default=str, indent=2), log_id),
        )
        masked += 1
    _logger.info("TFHKA: masked the token in %s /Autenticacion API log entries", masked)
