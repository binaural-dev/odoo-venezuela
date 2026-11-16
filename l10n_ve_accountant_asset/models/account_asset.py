from odoo import models


class AccountAsset(models.Model):
    _inherit = "account.asset"

    def compute_depreciation_board(self, date=False):
        """
        Las cuotas futuras se guardan con date = hoy y ``auto_post='custom'`` (su fecha real
        está en ``auto_post_custom_date``), por lo que la limpieza de enterprise, que filtra
        por ``move.date``, no las borraría y quedarían duplicadas. Se borran aquí por su
        fecha real antes de delegar al super.
        """
        stale_drafts = self.depreciation_move_ids.filtered(
            lambda mv: mv.state == "draft"
            and mv.auto_post == "custom"
            and (not date or (mv.auto_post_custom_date and mv.auto_post_custom_date >= date))
        )
        stale_drafts.unlink()
        # ``date`` solo se pasa si viene con valor: otros overrides de la cadena (p. ej.
        # binaural_account_asset) definen ``compute_depreciation_board(self)`` sin parámetro,
        # y pasárselo siempre rompería ``validate()``, que lo llama sin fecha.
        if date:
            return super().compute_depreciation_board(date)
        return super().compute_depreciation_board()
