from odoo import api, fields, models, _

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    _sql_constraints = [
        (
            "advance_customer_account_id",
            "unique(advance_customer_account_id)",
            "The advance customer account must be unique",
        ),
        (
            "advance_supplier_account_id",
            "unique(advance_supplier_account_id)",
            "The advance supplier account must be unique",
        ),
    ]

    advance_customer_account_id = fields.Many2one(
        related="company_id.advance_customer_account_id", readonly=False, store=True
    )
    advance_supplier_account_id = fields.Many2one(
        related="company_id.advance_supplier_account_id", readonly=False, store=True
    )
