from odoo import api, models

RATE_FIELDS = ("foreign_rate", "foreign_inverse_rate")


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        """
        Las cuotas de depreciación (``asset_move_type == 'depreciation'``) llevan como tasa
        manual la de la fecha de adquisición del activo (última tasa anterior a esa fecha,
        ver ``account.asset._get_acquisition_rate_values``). Nacen con su fecha real: el
        core las deja con ``auto_post='at_date'`` si son futuras y el cron nativo las publica
        ese día sin recalcular la tasa, de modo que el valor alterno no cambia al publicar.

        Se pisa también la tasa de la factura de compra que fija ``binaural_account_asset``
        (no es dependencia). Los valores se toman tal cual de ``compute_rate``. Si no existe
        ninguna tasa anterior lanza el UserError original y no se crea ninguna cuota.

        Fuera de alcance: los demás tipos (``negative_revaluation``, ``disposal``,
        ``modify`` con moneda distinta, etc.) se dejan como los devuelve el super.
        """
        move_vals = super()._prepare_move_for_asset_depreciation(vals)
        if move_vals.get("asset_move_type") == "depreciation":
            rate_values = vals["asset_id"]._get_acquisition_rate_values()
            if rate_values:
                move_vals.update(
                    {
                        "manually_set_rate": True,
                        **{fname: rate_values[fname] for fname in RATE_FIELDS},
                    }
                )
        return move_vals
