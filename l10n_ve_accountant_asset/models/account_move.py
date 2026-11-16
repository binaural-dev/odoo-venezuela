from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        """
        Las cuotas de depreciación de periodos que aún no terminan quedan en borrador con la
        fecha de hoy del usuario, ``auto_post='custom'`` y ``auto_post_custom_date`` con la
        fecha real del periodo: el cron de l10n_ve_accountant las publica ese día.
        ``asset_depreciation_beginning_date`` no se toca.

        Solo se modifica el diccionario del super, sin asumir claves adicionales: otros
        módulos (p. ej. binaural_account_asset) pueden haber agregado la tasa manual. Este
        módulo no establece tasas.
        """
        move_vals = super()._prepare_move_for_asset_depreciation(vals)
        today = fields.Date.context_today(self)
        if (
            move_vals.get("asset_move_type") == "depreciation"
            and not move_vals.get("asset_value_change")
            and move_vals.get("date")
            and move_vals["date"] > today
        ):
            move_vals.update(
                {
                    "date": today,
                    "auto_post": "custom",
                    "auto_post_custom_date": move_vals["date"],
                }
            )
        return move_vals
