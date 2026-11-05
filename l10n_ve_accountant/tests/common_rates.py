def set_rate(env, currency, date, company, inverse_rate):
    """Create the `currency` rate of `date` for `company`, or update it if it
    already exists, so test fixtures can ensure a rate without clashing."""
    Rate = env["res.currency.rate"]
    rate = Rate.search(
        [
            ("name", "=", date),
            ("currency_id", "=", currency.id),
            ("company_id", "=", company.id),
        ],
        limit=1,
    )
    if rate:
        rate.write({"inverse_company_rate": inverse_rate})
        return rate
    return Rate.create(
        {
            "name": date,
            "currency_id": currency.id,
            "inverse_company_rate": inverse_rate,
            "company_id": company.id,
        }
    )
