from unittest.mock import patch

from odoo import fields


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


def make_compute_rate_tolerant(test_case, env):
    """Evita que ``res.currency.rate.compute_rate()`` reviente con "no rate
    assigned" cuando un test usa una fecha/moneda para la que no sembro
    ninguna tasa -- incluye fechas calculadas en runtime (ej.
    ``fields.Date.today() - timedelta(days=3)``) que ningun seed fijo puede
    prever, y monedas puntuales (GBP, etc.) no contempladas arriba. Si
    existe una tasa real para esa fecha/moneda, se sigue devolviendo esa (no
    tapa tests que dependen de un valor sembrado especifico); solo cuando no
    encuentra nada se devuelve un valor dummy (1.0/1.0) en vez de levantar
    ``UserError``."""
    Rate = type(env["res.currency.rate"])
    original = Rate.compute_rate

    def _tolerant(self, foreign_currency_id, rate_date, raise_if_not_found=True):
        if not foreign_currency_id:
            return original(self, foreign_currency_id, rate_date, raise_if_not_found)
        return original(
            self, foreign_currency_id, rate_date, raise_if_not_found=False
        ) or {"foreign_rate": 1.0, "foreign_inverse_rate": 1.0}

    patcher = patch.object(Rate, "compute_rate", _tolerant)
    patcher.start()
    test_case.addCleanup(patcher.stop)
