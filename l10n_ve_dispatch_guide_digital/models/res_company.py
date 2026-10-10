from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def write(self, vals):
        # "Exigir datos de transporte" solo se configura con la guía digital
        # activa: al apagarla (o al apagar la facturación digital, que la
        # apaga) no debe quedar una exigencia activa que ya no se ve.
        if "dispatch_guide_digital_tfhka" in vals and not vals["dispatch_guide_digital_tfhka"]:
            vals = dict(vals, transport_data_required=False)
        return super().write(vals)
