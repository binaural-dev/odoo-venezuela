from odoo import api, models

RATE_FIELDS = ("foreign_rate", "foreign_inverse_rate")


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        """
        Las cuotas de depreciación (``asset_move_type == 'depreciation'``) llevan como tasa
        manual la efectiva del activo (ver ``account.asset._get_acquisition_rate_values``: su
        tasa propia si es > 0, la que fija ``binaural_account_asset`` (no es dependencia)
        desde la factura de compra; si no, la última tasa de la tabla anterior o igual a la
        fecha de adquisición). Nacen con su fecha real: el core las deja con
        ``auto_post='at_date'`` si son futuras y el cron nativo las publica ese día sin
        recalcular la tasa, de modo que el valor alterno no cambia al publicar.

        Los valores se toman tal cual. Si el activo no tiene tasa propia ni hay tasa en la
        tabla (o falta la fecha de adquisición) lanza un UserError y no se crea ninguna cuota.

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
