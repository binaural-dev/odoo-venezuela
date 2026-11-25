from odoo import models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _get_non_invoice_foreign_value(self):
        """Para las cuotas de depreciación, la tasa manual del activo manda sobre la del día.

        Vive aquí porque ``l10n_ve_accountant`` no depende de ``account_asset``. Si no
        aplica (no es una cuota, o no hay tasa manual) delega al ``super``.
        """
        self.ensure_one()
        rate = self._get_depreciation_manual_rate()
        if not rate:
            return super()._get_non_invoice_foreign_value()
        company = self.company_id
        return company.foreign_currency_id.round((self.debit - self.credit) / rate)

    def _get_depreciation_manual_rate(self):
        """Tasa manual de la cuota de depreciación a la que pertenece la línea, o 0.0 si
        debe usarse la tasa del día.

        ``foreign_rate`` es siempre unidades de la moneda de la compañía por unidad de la
        alterna (``compute_rate`` usa el ``inverse_company_rate`` de la alterna), sea esta
        USD o VEF, así que el valor alterno es siempre ``balance / foreign_rate``. No se usa
        ``foreign_inverse_rate`` (truncado a 6 decimales en el activo) ni se infiere la
        orientación con ``max()``, que solo acertaba con alterna USD.
        """
        move = self.move_id
        seen = set()
        while move.reversed_entry_id and move.id not in seen:
            seen.add(move.id)
            move = move.reversed_entry_id
        if not (
            move.asset_id
            and move.asset_move_type == "depreciation"
            and move.manually_set_rate
        ):
            return 0.0
        return abs(move.foreign_rate or 0.0)
