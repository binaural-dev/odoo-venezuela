from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    advance_customer_account_id = fields.Many2one(
        related="company_id.advance_customer_account_id", readonly=False, store=True
    )
    advance_supplier_account_id = fields.Many2one(
        related="company_id.advance_supplier_account_id", readonly=False, store=True
    )
