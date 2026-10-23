from odoo import fields


def seed_usd_rate(env, dates=None, rate=390.2944):
    """Siembra la tasa USD para cada fecha de `dates` (por defecto hoy) si no existe.

    Desde 94655dba7 (odoo-venezuela, maintenance-19.0, 2026-10-21)
    res.currency.rate.compute_rate() solo usa la tasa de la fecha exacta y
    levanta UserError si no hay una, en vez de caer en la más cercana
    anterior. Los tests que crean facturas con una fecha para la que
    ningún fixture creó tasa fallaban con "There is no rate assigned for
    USD on <fecha>". Se puede quitar si algún día ese comportamiento cambia.

    Las tasas solo viven en la compañía raíz (ver _check_company_id en el
    core), por eso se usa root_id.
    """
    company = env.company.root_id or env.company
    usd = env.ref("base.USD")
    Rate = env["res.currency.rate"]
    for date in dates or [fields.Date.today()]:
        date = fields.Date.to_date(date)
        if Rate.search(
            [
                ("currency_id", "=", usd.id),
                ("company_id", "=", company.id),
                ("name", "=", date),
            ],
            limit=1,
        ):
            continue
        Rate.create(
            {
                "currency_id": usd.id,
                "company_id": company.id,
                "name": date,
                "rate": 1 / rate,
                "company_rate": 1 / rate,
                "inverse_company_rate": rate,
            }
        )
