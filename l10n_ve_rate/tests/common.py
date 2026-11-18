from datetime import date, timedelta

from odoo import fields


def ensure_daily_rates(
    env, currency, company=None, rate=None, date_from=None, date_to=None, dates=None
):
    """Give `currency` a rate on every day from `date_from` to `date_to` for `company`.

    The localization looks the rate up only on the exact date of the document
    (``res.currency.rate.compute_rate``) and stops with "There is no rate assigned"
    when there is none, while the core converts with the latest rate on or before
    the date (1 when there is none). A clean database, like the one of the CI, has
    no rates: tests that only need *a* rate on the dates they use call this in their
    setUp instead of depending on the rates of the database they run on.

    Each missing day gets the rate the core would use that day anyway: the latest
    rate before it, or the first one after it when there is none before, or
    ``rate`` (1 by default) when the currency has no rate at all. So the amounts
    the core computes do not change, and days that already have a rate keep it:
    call this after the test creates its own rates.

    :param rate: units of ``currency`` per unit of the company currency (the
        ``rate`` column) for a currency without any rate. Default 1, as the core.
    :param date_from: first day, by default 2000-01-01 (tests use dates as old as 2006).
    :param date_to: last day, by default 400 days after today.
    :param dates: only these days instead of the range, for tests that create their
        own rates on other days later (a rate already given would clash with them).
    """
    company = company or env.company
    if dates is not None:
        days = sorted({fields.Date.to_date(day) for day in dates})
    else:
        first = date_from or date(2000, 1, 1)
        last = date_to or fields.Date.context_today(env.user) + timedelta(days=400)
        days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    env.flush_all()
    env.cr.execute(
        """
        INSERT INTO res_currency_rate
               (name, rate, currency_id, company_id, create_uid, write_uid, create_date, write_date)
        SELECT day::date,
               COALESCE(
                   (SELECT r.rate FROM res_currency_rate r
                     WHERE r.currency_id = %(currency)s
                       AND (r.company_id = %(company)s OR r.company_id IS NULL)
                       AND r.name < day::date
                  ORDER BY r.name DESC, r.company_id NULLS LAST LIMIT 1),
                   (SELECT r.rate FROM res_currency_rate r
                     WHERE r.currency_id = %(currency)s
                       AND (r.company_id = %(company)s OR r.company_id IS NULL)
                       AND r.name > day::date
                  ORDER BY r.name, r.company_id NULLS LAST LIMIT 1),
                   %(rate)s),
               %(currency)s, %(company)s, %(uid)s, %(uid)s, now(), now()
          FROM unnest(%(days)s::date[]) AS day
        ON CONFLICT DO NOTHING
        """,
        {
            "rate": rate or 1.0,
            "currency": currency.id,
            "company": company.id,
            "uid": env.uid,
            "days": days,
        },
    )
    env.invalidate_all()
