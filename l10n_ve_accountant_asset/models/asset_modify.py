from odoo import models


class AssetModify(models.TransientModel):
    _inherit = "asset.modify"

    def modify(self):
        """
        Deja pasar las cuotas futuras (``auto_post='custom'``) por el chequeo de enterprise
        "unposted depreciations prior to the selected operation date".

        Esas cuotas tienen como date la fecha de adquisición del activo, así que el chequeo
        (borrador y ``date <= self.date``) bloquearía toda modificación fechada desde la
        adquisición. Las que tienen su fecha real
        (``auto_post_custom_date``) posterior a la de la operación recuperan esa fecha: son
        periodos futuros pendientes, igual que un borrador futuro normal. El flujo de
        enterprise luego borra todos los borradores y recalcula el plan. Las de fecha real
        anterior o igual a la operación siguen bloqueando, como corresponde.
        """
        self.ensure_one()
        if not self.env.context.get("resume_after_pause"):
            future_drafts = self.asset_id.depreciation_move_ids.filtered(
                lambda mv: mv.state == "draft"
                and mv.auto_post == "custom"
                and mv.auto_post_custom_date
                and mv.auto_post_custom_date > self.date
            )
            for move in future_drafts:
                move.date = move.auto_post_custom_date
        return super().modify()
