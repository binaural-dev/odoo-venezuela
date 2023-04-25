from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    advance_payment_igtf_journal_id = fields.Many2one(
        related="company_id.advance_payment_igtf_journal_id", readonly=False, store=True
    )