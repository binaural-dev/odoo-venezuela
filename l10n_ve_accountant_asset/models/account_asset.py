from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

RATE_FIELDS = ("foreign_rate", "foreign_inverse_rate")


class AccountAsset(models.Model):
    _inherit = "account.asset"

    def _get_acquisition_rate_values(self):
        """Tasa de la fecha de adquisición del activo, tal cual la devuelve ``compute_rate``
        (``foreign_rate`` y ``foreign_inverse_rate``), o ``{}`` si la compañía no tiene
        moneda alterna.

        Sin ``raise_if_not_found``: si no hay tasa exacta en esa fecha lanza el UserError
        original de l10n_ve_rate y no se crea ninguna cuota.
        """
        self.ensure_one()
        company = self.company_id
        if not company.foreign_currency_id:
            return {}
        return (
            self.env["res.currency.rate"]
            .with_company(company)
            .compute_rate(company.foreign_currency_id.id, self.acquisition_date)
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
        Las cuotas futuras se guardan con date = fecha de adquisición y ``auto_post='custom'``
        (su fecha real está en ``auto_post_custom_date``), por lo que la limpieza de
        enterprise, que filtra por ``move.date``, no las borraría según su periodo y quedarían
        duplicadas. Se borran aquí por su fecha real antes de delegar al super.

        Las cuotas de depreciación llevan la tasa de la fecha de adquisición (ver
        ``_prepare_move_for_asset_depreciation``). ``binaural_account_asset`` (no es
        dependencia) escribe después del super la tasa del activo en TODAS las cuotas, también
        las ya publicadas, así que: antes del super se deja en el activo la tasa de
        adquisición para que esa escritura copie nuestro valor sea cual sea el orden del MRO;
        y después se corrige lo que difiera, restaurando las publicadas a como estaban. Solo
        se escribe si algo cambia (evita mensajes "rate updated" y recálculos).

        Fuera de alcance: ``negative_revaluation``, ``disposal`` y ``modify`` con moneda
        distinta.
        """
        acquisition_rates = {asset: asset._get_acquisition_rate_values() for asset in self}
        stale_drafts = self.depreciation_move_ids.filtered(
            lambda mv: mv.state == "draft"
            and mv.auto_post == "custom"
            and (not date or (mv.auto_post_custom_date and mv.auto_post_custom_date >= date))
        )
        stale_drafts.unlink()
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
            for move in asset.depreciation_move_ids.filtered(
                lambda mv: mv.state == "draft" and mv.asset_move_type == "depreciation"
            ):
                if not move.manually_set_rate or asset._rate_differs(move, rates):
                    move.write({"manually_set_rate": True, **rates})
        return result

    @api.constrains("depreciation_move_ids")
    def _check_depreciations(self):
        """Igual que enterprise pero tomando como última cuota la del último periodo real
        (``_asset_period_sort_key``), no la de mayor ``date``: los borradores 'custom' llevan
        la fecha de adquisición y quedarían antes de las ya publicadas."""
        for asset in self:
            if (
                asset.state == "open"
                and asset.depreciation_move_ids
                and not asset.currency_id.is_zero(
                    asset.depreciation_move_ids.sorted(
                        lambda move: move._asset_period_sort_key()
                    )[-1].asset_remaining_value
                )
            ):
                raise UserError(_("The remaining value on the last depreciation line must be 0"))

    def _create_move_before_date(self, date):
        """Antes de pausar, vender o modificar, devuelve a los borradores 'custom' su fecha
        real.

        ``_create_move_before_date`` de enterprise decide desde qué fecha empieza el tramo a
        depreciar mirando los borradores con ``move.date > última cuota publicada``. Con la
        fecha de adquisición como fecha contable esos borradores quedarían fuera y el tramo
        arrancaría en el inicio del activo (doble depreciación). Enterprise borra todos los
        borradores a continuación, así que restaurar la fecha no deja rastro.
        """
        for move in self.depreciation_move_ids.filtered(
            lambda mv: mv.state == "draft"
            and mv.auto_post == "custom"
            and mv.auto_post_custom_date
            and mv.date != mv.auto_post_custom_date
        ):
            move.date = move.auto_post_custom_date
        return super()._create_move_before_date(date)
