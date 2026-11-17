from odoo import fields


class ForeignRateFixture:
    """Tasa de la moneda alterna para las fechas que usa una prueba.

    `res.currency.rate.compute_rate` (l10n_ve_rate) solo usa la tasa de la fecha exacta y falla con
    "There is no rate assigned" si no existe. Una prueba que crea facturas sin crear tasas
    queda en error en una base limpia: se llama al final de su `setUp`, cuando la compañía ya tiene
    su moneda y su moneda alterna. El valor de la tasa da igual a estas pruebas: no revisan montos
    en moneda alterna."""

    def _set_foreign_rates(self, dates=(), rate=1.0, currency=None):
        """`currency`: la moneda que recibe la tasa; por defecto la alterna de la compañía."""
        company = self.company
        currency = currency or company.foreign_currency_id
        Rate = self.env["res.currency.rate"]
        for date in {fields.Date.today(), *map(fields.Date.to_date, dates)}:
            if not Rate.search_count([
                ("currency_id", "=", currency.id),
                ("company_id", "=", company.id),
                ("name", "=", date),
            ]):
                Rate.create({
                    "name": date,
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "company_rate": rate,
                })
