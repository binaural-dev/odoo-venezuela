from odoo import models
from odoo.tools import float_compare

RATE_FIELDS = ("foreign_rate", "foreign_inverse_rate")


class AccountAsset(models.Model):
    _inherit = "account.asset"

    def _get_acquisition_rate_values(self):
        """Tasa de la fecha de adquisición del activo, tal cual la devuelve ``compute_rate``
        (``foreign_rate`` y ``foreign_inverse_rate``), o ``{}`` si la compañía no tiene
        moneda alterna.

        Si en esa fecha no hay tasa se usa la última anterior (``use_last_rate``: fin de
        semana o feriado). Si no existe ninguna tasa anterior lanza el UserError original de
        l10n_ve_rate y no se crea ninguna cuota.
        """
        self.ensure_one()
        company = self.company_id
        if not company.foreign_currency_id:
            return {}
        return (
            self.env["res.currency.rate"]
            .with_company(company)
            .compute_rate(
                company.foreign_currency_id.id,
                self.acquisition_date,
                raise_if_not_found=True,
                use_last_rate=True,
            )
        )

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
        Las cuotas de depreciación llevan la tasa de la fecha de adquisición (ver
        ``account.move._prepare_move_for_asset_depreciation``). ``binaural_account_asset`` (no
        es dependencia) escribe después del super la tasa del activo en TODAS las cuotas,
        también las ya publicadas, así que: antes del super se deja en el activo la tasa de
        adquisición para que esa escritura copie nuestro valor sea cual sea el orden del MRO;
        y después se restauran las publicadas a como estaban y se corrigen las cuotas nuevas (los
        borradores y las que este mismo plan acaba de publicar) que difieran. Solo se escribe
        si algo cambia (evita mensajes "rate updated" y
        recálculos).

        Fuera de alcance: ``negative_revaluation``, ``disposal`` y ``modify`` con moneda
        distinta.
        """
        acquisition_rates = {asset: asset._get_acquisition_rate_values() for asset in self}
        if "foreign_rate" in self._fields:
            for asset, rates in acquisition_rates.items():
                if rates and asset._rate_differs(asset, rates):
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
