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

        La tasa se expresa siempre como unidades de la moneda más débil por 1
        unidad de la más fuerte (p. ej. Bs por USD), sin importar cuál de las dos
        es la moneda de la compañía: una compañía en VES ve lo mismo que una en
        USD que eligió VES.

        Returns
        -------
        dict
            ``{}`` si el systray no aplica a la compañía (desactivado o sin moneda
            configurada). Si no, ``rate`` (unidades de ``currency`` por 1 unidad de
            ``foreign_currency``; ``False`` si no hay ninguna tasa), ``date``
            (``YYYY-MM-DD`` o ``False``), ``is_today``, ``currency`` /
            ``currency_symbol`` (la moneda en la que se expresa la tasa, p. ej. Bs)
            y ``foreign_currency`` / ``foreign_currency_symbol`` (la unidad, p. ej.
            USD).
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

        # company_rate = unidades de la moneda elegida por 1 unidad de la compañía.
        # Si es >= 1 la moneda elegida es la débil (compañía en USD que muestra Bs);
        # si no, la débil es la de la compañía (compañía en Bs que muestra USD).
        if rate and rate.company_rate >= 1:
            value, shown, unit = rate.company_rate, foreign, company.currency_id
        else:
            value = rate.inverse_company_rate if rate else False
            shown, unit = company.currency_id, foreign

        return {
            "rate": value,
            "date": fields.Date.to_string(rate.name) if rate else False,
            "is_today": bool(rate) and rate.name == today,
            "currency": shown.name,
            "currency_symbol": shown.symbol,
            "foreign_currency": unit.name,
            "foreign_currency_symbol": unit.symbol,
        }
