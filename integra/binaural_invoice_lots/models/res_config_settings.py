from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    batchs_journal_id = fields.Many2one(related="company_id.batchs_journal_id", readonly=False)
