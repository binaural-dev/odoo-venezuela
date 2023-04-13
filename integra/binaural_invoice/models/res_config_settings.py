from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    max_product_invoice = fields.Integer(related="company_id.max_product_invoice", readonly=False)
    group_sales_invoicing_series = fields.Boolean(
        "Series Invoicing",
        related="company_id.group_sales_invoicing_series",
        readonly=False,
        implied_group="binaural_invoice.group_sales_invoicing_series",
    )
