from odoo import fields, models


class ForeignCurrencyConvertMixin(models.AbstractModel):
    """Comparte la lógica de conversión de moneda comercial -> moneda de la
    compañía entre crm.lead y crm.team, para no duplicarla en cada modelo.
    Los modelos que lo usan deben tener foreign_currency_id y company_id."""

    _name = "l10n.ve.crm.foreign.currency.mixin"
    _description = "Mixin de conversión de moneda comercial"

    def _convert_foreign_to_company(self, amount_foreign):
        """Convierte un monto en moneda comercial a la moneda de la compañía
        usando la tasa vigente. No modifica el monto en moneda comercial."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if not amount_foreign or not self.foreign_currency_id or not company.currency_id:
            return 0.0
        return self.foreign_currency_id._convert(
            amount_foreign,
            company.currency_id,
            company,
            fields.Date.context_today(self),
        )
