from odoo import api, models


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model
    def _bcv_sync_upsert(self, currency, company, rate_date, value):
        """Idempotently creates or updates the ``res.currency.rate`` of
        ``currency`` for ``company``/``rate_date``.

        The upsert key is exactly ``(currency_id, company_id, name)``,
        which is also the native unique constraint of ``res.currency.rate``
        (``unique_name_per_day``) -- that's why retries of the same BCV
        Sync payload never create a duplicate record, only update it.

        ``value`` is the number BCV publishes: "VEF units per 1 unit of
        ``currency``" (e.g. 791.6667 VEF per 1 USD). It's written to
        ``inverse_company_rate``, the Odoo field that represents exactly
        that ("units of the company's currency per 1 unit of this
        currency") as long as ``company``'s accounting currency is VEF --
        a precondition already verified by the caller
        (``res.company._bcv_sync_process_tasas``).

        Rate records are always stored against the root company
        (``company.root_id``), matching the native behavior of
        ``res.currency.rate`` (child companies inherit their root
        company's rate) and because ``res.currency.rate`` doesn't allow
        creating rates for non-root companies.
        """
        root_company = company.root_id
        existing = self.search(
            [
                ("currency_id", "=", currency.id),
                ("company_id", "=", root_company.id),
                ("name", "=", rate_date),
            ],
            limit=1,
        )
        if existing:
            existing.inverse_company_rate = value
            return existing

        return self.create(
            {
                "currency_id": currency.id,
                "company_id": root_company.id,
                "name": rate_date,
                "inverse_company_rate": value,
            }
        )
