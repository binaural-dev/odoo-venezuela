from odoo import api, fields, models


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model
    def get_systray_rate(self):
        """Última tasa de la moneda configurada en la compañía activa, para el systray.

        Solo aplica si la compañía activó ``show_rate_systray`` y eligió una moneda
        (``rate_systray_currency_id``) distinta a la suya. Busca la tasa más
        reciente con fecha menor o igual a hoy (fecha del usuario); las tasas
        futuras no cuentan. Igual que ``res.currency._get_rates``, prefiere la
        tasa de la compañía, luego la de su raíz (una sucursal resuelve la de su
        matriz) y por último las tasas sin compañía.

        Returns
        -------
        dict
            ``{}`` si el systray no aplica a la compañía (desactivado o sin moneda
            configurada). Si no, ``rate`` (unidades de moneda de la compañía por 1
            unidad foránea, p. ej. Bs por USD; ``False`` si no hay ninguna tasa),
            ``date`` (``YYYY-MM-DD`` o ``False``), ``is_today`` y los
            símbolos/códigos de ambas monedas.
        """
        company = self.env.company
        foreign = company.rate_systray_currency_id
        if not company.show_rate_systray or not foreign or foreign == company.currency_id:
            return {}

        today = fields.Date.context_today(self)
        rate = self.browse()
        for company_id in [*dict.fromkeys((company | company.root_id).ids), False]:
            rate = self.search(
                [
                    ("currency_id", "=", foreign.id),
                    ("company_id", "=", company_id),
                    ("name", "<=", today),
                ],
                order="name desc",
                limit=1,
            )
            if rate:
                break

        return {
            "rate": rate.inverse_company_rate if rate else False,
            "date": fields.Date.to_string(rate.name) if rate else False,
            "is_today": bool(rate) and rate.name == today,
            "currency": company.currency_id.name,
            "currency_symbol": company.currency_id.symbol,
            "foreign_currency": foreign.name,
            "foreign_currency_symbol": foreign.symbol,
        }
