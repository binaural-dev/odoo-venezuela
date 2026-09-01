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

        - the currency isn't active/used in this Odoo (only currencies the
          company actually has enabled are considered, see
          ``currency_model`` below);
        - the value can't be parsed as a positive number;
        - fecha_valor doesn't have a valid format;
        - ``_bcv_sync_is_valid_rate_date`` (this module's own date logic,
          see below) rejects fecha_valor for today;
        - fecha_valor is today and this company already has a stored rate
          for today -- once today's rate is set, later runs the same day
          never change it (accounting stability: a rate in effect during
          the day must not silently change under transactions already
          posted). This does not apply to advance (future) dates, which
          keep getting refreshed on every run until they become "today".

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
        # No `active_test=False` here on purpose: only currencies the
        # company actually has active/enabled are considered. A currency
        # BCV Sync sends that this Odoo never turned on is skipped, not
        # silently tracked.
        currency_model = self.env["res.currency"].sudo()
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

            if not self._bcv_sync_is_valid_rate_date(today, published_date):
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

            if published_date == today and rate_model.search_count(
                [
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", self.id),
                    ("name", "=", today),
                ]
            ):
                _logger.info(
                    "BCV Sync: %s already has a stored rate for today "
                    "(%s), keeping the existing value.",
                    moneda,
                    today,
                )
                skipped.append(moneda)
                continue

            rate_model._bcv_sync_upsert(currency, self, published_date, value)
            applied.append(moneda)

        return {"applied": applied, "skipped": skipped}

    def _bcv_sync_is_valid_rate_date(self, current_date, published_date):
        """Decides whether ``published_date`` should be applied as
        today's rate for this company. Fully self-contained to this
        module -- it does not call ``l10n_ve_currency_rate_live``'s own
        ``_is_valid_rate_date`` (that method's past-date branch exists
        for a different caller, that module's own scraping/fallback
        flow). The only thing reused from that module is the
        ``can_update_habil_days`` field itself.

        - ``published_date`` is today: always valid -- BCV's own rate for
          today always applies, regardless of the flag.
        - ``published_date`` is in the future: valid only if
          ``can_update_habil_days`` is enabled. BCV publishes the next
          business day's rate in advance (e.g. Friday afternoon for
          Monday, or for Tuesday directly if Monday is a bank holiday).
          When the flag is disabled, an advance rate is rejected --
          nothing gets written, so the last stored rate simply stays in
          effect.
        - ``published_date`` is in the past: always invalid, regardless
          of the flag. BCV Sync's feed never legitimately carries a past
          date (BCV's own site always shows today's rate or an advance
          one, never a stale one), so this endpoint never backdates an
          existing rate record.
        """
        if published_date == current_date:
            return True
        if published_date > current_date:
            return bool(self.can_update_habil_days)
        return False

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
