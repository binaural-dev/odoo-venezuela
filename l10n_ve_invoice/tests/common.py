from odoo import fields

from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate


class RateSeedMixin:
    """Siembra la tasa de la moneda alterna para las fechas que usa un test.

    `res.currency.rate.compute_rate` (l10n_ve_rate) busca la tasa SOLO en la
    fecha exacta del documento y lanza un UserError si no existe. Una base de
    tests sin datos demo no trae tasas, así que cualquier factura creada con
    moneda alterna falla en `create` ("There is no rate assigned for ...").

    Requiere `self.company` con `foreign_currency_id` ya configurada.
    """

    def _seed_foreign_rates(self, *rate_dates, rate=40.0):
        company = self.company
        currency = company.foreign_currency_id
        if not currency or currency == company.currency_id:
            return
        for rate_date in rate_dates:
            set_rate(
                self.env, currency, fields.Date.to_date(rate_date), company.root_id, rate
            )
