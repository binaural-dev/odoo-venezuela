from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_binaural_pos_igtf = fields.Boolean(
        related="company_id.module_binaural_pos_igtf", readonly=False
    )
    module_binaural_base_igtf = fields.Boolean(
        related="company_id.module_binaural_base_igtf", readonly=False
    )
    module_binaural_pos_mf = fields.Boolean(
        related="company_id.module_binaural_pos_mf", readonly=False
    )
    receipt_journal_id = fields.Many2one(
        "account.journal", related="pos_config_id.receipt_journal_id", readonly=False
    )
    always_invoice = fields.Boolean(related="pos_config_id.always_invoice", readonly=False)
