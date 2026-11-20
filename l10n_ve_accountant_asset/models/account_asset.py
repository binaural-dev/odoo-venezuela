from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

RATE_FIELDS = ("foreign_rate", "foreign_inverse_rate")


class AccountAsset(models.Model):
    _inherit = "account.asset"

    def _get_own_rate_values(self):
        """Tasa propia del activo tal cual está guardada (``foreign_rate`` y
        ``foreign_inverse_rate``), o ``{}`` si el campo no existe.

        Esos campos los define ``binaural_account_asset`` (no es dependencia), que copia en
        ellos la tasa de la factura de compra. Es el único punto del puente que los lee, así
        los tests pueden emular el campo sin el addon.
        """
        self.ensure_one()
        if "foreign_rate" not in self._fields:
            return {}
        return {fname: self[fname] for fname in RATE_FIELDS}

    def _has_own_rate(self):
        """True si el activo trae una tasa propia utilizable (``foreign_rate`` > 0)."""
        self.ensure_one()
        return (self._get_own_rate_values().get("foreign_rate") or 0.0) > 0

    def _get_acquisition_rate_values(self):
        """Tasa efectiva de las cuotas de depreciación (``foreign_rate`` y
        ``foreign_inverse_rate``), o ``{}`` si la compañía no tiene moneda alterna.

        Orden de resolución:

        1. Tasa propia del activo (``foreign_rate`` > 0, la de la factura de compra que fija
           ``binaural_account_asset``): se devuelve tal cual, sin consultar la tabla. Si su
           inversa está vacía se deriva con ``compute_inverse_rate``.
        2. Sin tasa propia, la de la tabla en la fecha de adquisición (``compute_rate``
           con ``use_last_rate``: si ese día no hay tasa, la última anterior, p. ej. fin de
           semana o feriado). Sin ninguna tasa en esa fecha ni antes, lanza un UserError y
           no se crea ninguna cuota.

        La guarda de "falta la fecha de adquisición" es defensiva: ``account.asset`` exige
        ``prorata_date`` (NOT NULL, derivada de ``acquisition_date``), así que un activo
        guardado siempre trae fecha; solo es alcanzable con registros virtuales.
        """
        self.ensure_one()
        company = self.company_id
        if not company.foreign_currency_id:
            return {}
        Rate = self.env["res.currency.rate"].with_company(company)
        if self._has_own_rate():
            own = self._get_own_rate_values()
            return {
                "foreign_rate": own["foreign_rate"],
                "foreign_inverse_rate": own["foreign_inverse_rate"]
                or Rate.compute_inverse_rate(own["foreign_rate"]),
            }
        if not self.acquisition_date:
            raise UserError(
                _(
                    "The acquisition date of the asset %(asset)s is missing. "
                    "Set it before confirming the asset.",
                    asset=self.display_name,
                )
            )
        rate_values = Rate.compute_rate(
            company.foreign_currency_id.id,
            self.acquisition_date,
            raise_if_not_found=False,
            use_last_rate=True,
        )
        if not rate_values:
            raise UserError(
                _(
                    "There is no %(currency)s rate on %(date)s or on earlier dates for the "
                    "asset %(asset)s. Load the rate and confirm the asset again.",
                    currency=company.foreign_currency_id.name,
                    date=self.acquisition_date,
                    asset=self.display_name,
                )
            )
        return rate_values

    def _rate_differs(self, move, values):
        """True si la tasa de ``move`` difiere de ``values`` a la precisión del campo."""
        return any(
            float_compare(
                record[fname],
                values[fname],
                precision_digits=record._fields[fname].get_digits(self.env)[1],
            )
            for record in move
            for fname in RATE_FIELDS
        )

    def compute_depreciation_board(self, date=False):
        """
        Las cuotas de depreciación llevan la tasa efectiva del activo (ver
        ``_get_acquisition_rate_values``: su tasa propia si es > 0; si no, la de la tabla en la
        fecha de adquisición) y ``account.move._prepare_move_for_asset_depreciation``.
        ``binaural_account_asset`` (no es dependencia) escribe después del super la tasa del
        activo en TODAS las cuotas, también las ya publicadas, así que: si el activo no
        tiene tasa propia, antes del super se le deja la de la tabla para que esa escritura copie
        nuestro valor sea cual sea el orden del MRO (si ya la tiene no se escribe nada en el
        activo); y después se restauran las publicadas a como estaban y se corrigen las
        cuotas nuevas (los borradores y las que este mismo plan acaba de publicar) que difieran.
        Solo se escribe si algo cambia (evita mensajes "rate updated" y recálculos).

        Fuera de alcance: ``negative_revaluation``, ``disposal`` y ``modify`` con moneda
        distinta.
        """
        acquisition_rates = {asset: asset._get_acquisition_rate_values() for asset in self}
        if "foreign_rate" in self._fields:
            for asset, rates in acquisition_rates.items():
                if rates and not asset._has_own_rate() and asset._rate_differs(asset, rates):
                    asset.write({fname: rates[fname] for fname in RATE_FIELDS})
        snapshot = {
            move: {
                "manually_set_rate": move.manually_set_rate,
                **{fname: move[fname] for fname in RATE_FIELDS},
            }
            for move in self.depreciation_move_ids.filtered(
                lambda mv: mv.state == "posted" and mv.asset_move_type == "depreciation"
            )
        }
        # ``date`` solo se pasa si viene con valor: otros overrides de la cadena (p. ej.
        # binaural_account_asset) definen ``compute_depreciation_board(self)`` sin parámetro,
        # y pasárselo siempre rompería ``validate()``, que lo llama sin fecha.
        if date:
            result = super().compute_depreciation_board(date)
        else:
            result = super().compute_depreciation_board()
        for move, old in snapshot.items():
            if move.exists() and any(move[fname] != value for fname, value in old.items()):
                move.write(old)
        for asset, rates in acquisition_rates.items():
            if not rates:
                continue
            values = {"manually_set_rate": True, **{fname: rates[fname] for fname in RATE_FIELDS}}
            for move in asset.depreciation_move_ids.filtered(
                lambda mv: mv not in snapshot
                and mv.state != "cancel"
                and mv.asset_move_type == "depreciation"
            ):
                if not move.manually_set_rate or asset._rate_differs(move, rates):
                    move.write(values)
        return result
