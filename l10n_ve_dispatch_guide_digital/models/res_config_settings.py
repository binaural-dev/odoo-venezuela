from odoo import api, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.onchange("dispatch_guide_digital_tfhka")
    def _onchange_dispatch_guide_digital_tfhka_transport(self):
        if not self.dispatch_guide_digital_tfhka:
            self.transport_data_required = False
