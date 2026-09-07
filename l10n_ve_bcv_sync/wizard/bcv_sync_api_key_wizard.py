from odoo import fields, models


class BcvSyncApiKeyWizard(models.TransientModel):
    _name = "bcv.sync.api.key.wizard"
    _description = "BCV Sync API Key Wizard"

    token = fields.Char(string="Token Generado", readonly=True)
