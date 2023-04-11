from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_invoice_rate_from_sale_order = fields.Boolean(
        related="company_id.use_invoice_rate_from_sale_order",
        help=(
            "Check this if you want the rate of the invoice to be taken from its sale order."
            " Else it will take the rate of the date when it is created."
        ),
        readonly=False,
    )
