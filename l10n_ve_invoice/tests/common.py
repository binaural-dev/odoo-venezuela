from unittest.mock import patch

from odoo import api

NEUTRAL_FIXTURE_INVERSE_RATE = 1.0


def enable_historical_rate_fixtures(testcase):
    """`l10n_ve_rate` resolves a rate ONLY for the exact date it is asked for
    (`ResCurrencyRate.compute_rate`, no nearest/previous fallback) and raises
    when there is none. These fixtures create invoices on arbitrary dates
    without declaring a rate for each. For the duration of the test, when the
    exact-date rate is missing, it is created on the requested date from the
    most recent earlier rate of that currency (or a neutral one) and the real
    method is called. Production code is untouched.
    """
    rate_model = type(testcase.env["res.currency.rate"])
    original = rate_model.compute_rate

    @api.model
    def compute_rate(self, foreign_currency_id, rate_date, *args, **kwargs):
        company = self.env.company
        if foreign_currency_id and foreign_currency_id != company.currency_id.id:
            domain = [
                ("currency_id", "=", foreign_currency_id),
                ("company_id", "in", (company | company.root_id).ids),
            ]
            rates = self.env["res.currency.rate"].sudo()
            if not rates.search_count(domain + [("name", "=", rate_date)]):
                earlier = rates.search(
                    domain + [("name", "<=", rate_date)], order="name desc", limit=1
                )
                rates.create(
                    {
                        "currency_id": foreign_currency_id,
                        "company_id": earlier.company_id.id or company.root_id.id,
                        "name": rate_date,
                        "inverse_company_rate": earlier.inverse_company_rate
                        or NEUTRAL_FIXTURE_INVERSE_RATE,
                    }
                )
        return original(self, foreign_currency_id, rate_date, *args, **kwargs)

    patcher = patch.object(rate_model, "compute_rate", compute_rate)
    patcher.start()
    testcase.addCleanup(patcher.stop)
