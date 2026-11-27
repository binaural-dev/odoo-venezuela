from datetime import timedelta

from odoo import fields

from odoo.addons.l10n_ve_rate.tests.common import ensure_daily_rates


def seed_today_vef_rate(env, company, rate=38.0):
    """Crea una ``res.currency.rate`` fechada *hoy* para VEF y para USD.

    ``l10n_ve_accountant.account_move.create()`` llama
    ``res.currency.rate.compute_rate()`` sin condicion -- ni siquiera cuando
    la factura trae ``manually_set_rate=True`` -- usando
    ``fields.Date.today()`` porque un invoice recien creado todavia no tiene
    ``invoice_date`` (se asigna recien al postear). Sin una tasa sembrada
    para ese dia exacto, cualquier creacion de ``account.move`` en una base
    de test fresca (sin datos de demo, sin el cron que trae la tasa BCV del
    dia) revienta con "no rate assigned", sin importar que el test
    sobreescriba ``foreign_rate``/``foreign_inverse_rate`` a mano despues.
    El valor de ``rate`` no importa para estos tests -- solo que la fila
    exista para esa fecha.

    Se siembran ambas monedas (no solo VEF) porque algunos tests fuerzan la
    compañia a VEF (``_force_company_currency``), y ahi la moneda "foránea"
    detectada pasa a ser USD (la de la tarifa del partner), no VEF."""
    Rate = env["res.currency.rate"].sudo()
    for currency in (env.ref("base.VEF"), env.ref("base.USD")):
        currency.sudo().active = True
        Rate.create(
            {
                "name": fields.Date.today(),
                "currency_id": currency.id,
                "company_id": company.id,
                "rate": rate,
            }
        )


def seed_daily_rates(env, company, rate=38.0, days_before=60, days_after=2):
    """Da a VEF y a USD una tasa en ``company`` para cada dia de la ventana
    que usan las pruebas, ademas de la de hoy (``seed_today_vef_rate``).

    La localizacion busca la tasa solo en la fecha exacta del documento
    (``res.currency.rate.compute_rate``) y, si no la hay, se detiene con «no
    rate assigned», como en produccion. Las pruebas usan hoy (en UTC y en la
    zona del usuario, que a partir de las 8 pm de Caracas son dias distintos)
    y fechas hasta 46 dias atras, asi que cada uno de esos dias necesita su
    tasa. ``ensure_daily_rates`` le da a cada dia sin tasa la que Odoo usaria
    ese dia de todos modos (la ultima anterior, o la primera posterior), asi
    que los montos que calcula el nucleo no cambian, y no toca los dias que ya
    tienen una: se llama despues de crear las tasas propias de la prueba.
    """
    seed_today_vef_rate(env, company, rate=rate)
    today = fields.Date.context_today(env.user)
    for currency in (env.ref("base.VEF"), env.ref("base.USD")):
        ensure_daily_rates(
            env,
            currency,
            company=company,
            date_from=today - timedelta(days=days_before),
            date_to=today + timedelta(days=days_after),
        )
