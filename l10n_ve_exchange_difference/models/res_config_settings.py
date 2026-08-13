from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ve_exchange_use_nd_nc = fields.Boolean(
        related='company_id.l10n_ve_exchange_use_nd_nc',
        readonly=False,
    )
    l10n_ve_exchange_note_product_id = fields.Many2one(
        related='company_id.l10n_ve_exchange_note_product_id',
        readonly=False,
    )
