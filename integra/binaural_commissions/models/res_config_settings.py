from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    commission_product_id = fields.Many2one(
        "product.product", related="company_id.commission_product_id", readonly=False
    )
    commission_journal_id = fields.Many2one(
        "account.journal", related="company_id.commission_journal_id", readonly=False
    )
    commission_invoice_date_field = fields.Selection(
        related="company_id.commission_invoice_date_field",
        readonly=False,
    )
    compute_commission_when = fields.Selection(
        related="company_id.compute_commission_when", readonly=False
    )
    commission_payment_through = fields.Selection(
        related="company_id.commission_payment_through", readonly=False
    )
