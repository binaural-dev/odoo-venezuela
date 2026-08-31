import hmac
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# BCV publishes each rate as "VEF units per 1 unit of the foreign currency"
# (e.g. 791.6667 VEF per 1 USD). This module assumes the company's
# accounting currency (`currency_id`) is VEF -- that's the only case where
# this number can be written directly as `inverse_company_rate` without an
# extra cross-conversion. If a given company uses the "legacy"
# `l10n_ve_rate`/`l10n_ve_currency_rate_live` scheme (USD accounting
# currency, VEF as the "foreign" currency), this integration does not apply
# and is explicitly skipped (see `_bcv_sync_process_tasas`).
VEF_CURRENCY_CODE = "VEF"


class ResCompany(models.Model):
    _inherit = "res.company"

    bcv_sync_api_key = fields.Char(
        string="BCV Sync API Key",
        copy=False,
        groups="base.group_system",
        help=(
            "Token compartido que BCV Sync envia en el header "
            "'Authorization: Bearer <token>' al llamar a POST /api/tasas-bcv. "
            "Se puede generar desde aqui (boton 'Generar Token' en Ajustes) o "
            "pegar uno ya generado en el panel de BCV Sync; en ambos casos, "
            "el valor final debe coincidir exactamente con el configurado "
            "alli para el cliente/URL de esta compania."
        ),
    )

    @api.model
    def _bcv_sync_get_company_by_token(self, token):
        """Finds the company whose ``bcv_sync_api_key`` matches ``token``.

        Compares against every company with a key configured using
        ``hmac.compare_digest`` (constant time) so timing doesn't leak
        whether the received token is correct or not.
        """
        if not token:
            return self.browse()

        companies = self.sudo().with_context(active_test=False).search(
            [("bcv_sync_api_key", "!=", False)]
        )
        match = self.browse()
        for company in companies:
            if hmac.compare_digest(token, company.bcv_sync_api_key or ""):
                match = company
        return match

    def _bcv_sync_process_tasas(self, tasas):
        """Idempotently applies the ``tasas`` entries received from BCV
        Sync for this company (always runs against the root company, see
        the controller).

        Each ``tasas`` entry is a dict with ``moneda``/``valor``/
        ``fecha_valor`` exactly as they arrive in the payload (see
        ``ODOO_INTEGRATION.md`` in the BCV Sync repo). An entry is skipped
        -without aborting the rest of the payload- when:

        - the currency doesn't exist/isn't recognized in Odoo;
        - the value can't be parsed as a positive number;
        - fecha_valor doesn't have a valid format;
        - ``_is_valid_rate_date`` (inherited from
          ``l10n_ve_currency_rate_live``) determines that fecha_valor
          doesn't apply "today" (e.g. an advance rate for the next
          business day with ``can_update_habil_days`` disabled).

        Returns a summary ``{"applied": [...], "skipped": [...]}``
        (currency codes) only for the caller's logging/observability.
        """
        self.ensure_one()
        # Rates are always saved/queried against the root company (see
        # `res.currency.rate._bcv_sync_upsert`); make sure we also decide
        # against that same company, regardless of whether the token
        # matched a child company.
        self = self.root_id
        applied = []
        skipped = []

        if self.currency_id.name != VEF_CURRENCY_CODE:
            _logger.warning(
                "BCV Sync: company '%s' does not have VEF as its accounting "
                "currency (has '%s'); skipping the whole payload to avoid "
                "storing incorrect rates.",
                self.display_name,
                self.currency_id.name,
            )
            return {
                "applied": applied,
                "skipped": [entry.get("moneda") for entry in tasas],
            }

        today = fields.Date.context_today(self)
        currency_model = self.env["res.currency"].sudo().with_context(
            active_test=False
        )
        rate_model = self.env["res.currency.rate"].sudo()

        for entry in tasas:
            moneda = (entry.get("moneda") or "").strip().upper()

            currency = currency_model.search([("name", "=", moneda)], limit=1)
            if not currency:
                _logger.info(
                    "BCV Sync: currency '%s' not recognized, skipping that entry.",
                    moneda,
                )
                skipped.append(moneda)
                continue

            value = self._bcv_sync_parse_valor(entry.get("valor"))
            if value is None:
                _logger.warning(
                    "BCV Sync: invalid valor '%s' for %s, skipping that entry.",
                    entry.get("valor"),
                    moneda,
                )
                skipped.append(moneda)
                continue

            published_date = self._bcv_sync_parse_fecha_valor(
                entry.get("fecha_valor")
            )
            if not published_date:
                _logger.warning(
                    "BCV Sync: invalid fecha_valor '%s' for %s, skipping "
                    "that entry.",
                    entry.get("fecha_valor"),
                    moneda,
                )
                skipped.append(moneda)
                continue

            if not self._is_valid_rate_date(today, published_date):
                _logger.info(
                    "BCV Sync: fecha_valor %s for %s does not apply today "
                    "(%s) per can_update_habil_days=%s, skipping.",
                    published_date,
                    moneda,
                    today,
                    self.can_update_habil_days,
                )
                skipped.append(moneda)
                continue

            rate_model._bcv_sync_upsert(currency, self, published_date, value)
            applied.append(moneda)

        return {"applied": applied, "skipped": skipped}

    @api.model
    def _bcv_sync_parse_valor(self, raw_value):
        """``tasas[].valor`` arrives as a string to avoid losing precision.
        Returns a strictly positive ``float``, or ``None`` if it can't be
        parsed (never raises)."""
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @api.model
    def _bcv_sync_parse_fecha_valor(self, raw_date):
        """``tasas[].fecha_valor`` arrives as a ``YYYY-MM-DD`` string.
        Returns a ``date``, or ``None`` if it can't be parsed (never
        raises)."""
        if not raw_date:
            return None
        try:
            return fields.Date.to_date(raw_date)
        except ValueError:
            return None
