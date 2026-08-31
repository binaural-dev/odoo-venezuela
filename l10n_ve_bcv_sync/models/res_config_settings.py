import secrets

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bcv_sync_api_key = fields.Char(
        related="company_id.bcv_sync_api_key", readonly=False
    )

    def action_generate_bcv_sync_api_key(self):
        """Generates a random token, assigns it directly to
        ``company_id.bcv_sync_api_key``, and shows it once in a wizard so
        the admin can copy it into the BCV Sync panel (same pattern as
        ``binaural_splynx``)."""
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        self.bcv_sync_api_key = token
        wizard = self.env["bcv.sync.api.key.wizard"].create({"token": token})
        return {
            "type": "ir.actions.act_window",
            "res_model": "bcv.sync.api.key.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }
