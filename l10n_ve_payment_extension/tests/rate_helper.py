from datetime import timedelta

from odoo import fields


def seed_foreign_rate(env, date=None, rate=380.0, currency=None):
    """Seed the foreign-currency rate dated exactly `date` (default: today).

    `res.currency.rate.compute_rate()` only looks for a rate dated exactly the
    requested day and raises UserError when there is none (l10n_ve_rate), so a
    test that creates documents on a date needs a rate for that date. It is
    idempotent: an existing rate for that day is left untouched.

    Rates live in the root company (`_check_company_id`), hence `root_id`.
    """
    company = env.company.root_id or env.company
    currency = currency or company.foreign_currency_id or env.ref("base.USD")
    if currency == company.currency_id:
        return
    date = date or fields.Date.today()
    Rate = env["res.currency.rate"]
    exists = Rate.search(
        [
            ("currency_id", "=", currency.id),
            ("company_id", "=", company.id),
            ("name", "=", date),
        ],
        limit=1,
    )
    if not exists:
        Rate.create(
            {
                "currency_id": currency.id,
                "company_id": company.id,
                "name": date,
                "rate": 1 / rate,
                "inverse_company_rate": rate,
            }
        )


def seed_foreign_rates_between(env, date_from, date_to, **kwargs):
    """Seed one rate per day in [date_from, date_to], both included."""
    day = date_from
    while day <= date_to:
        seed_foreign_rate(env, day, **kwargs)
        day += timedelta(days=1)
