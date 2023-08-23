from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    do_not_show_products_without_availability_on_site = fields.Boolean(
        related="website_id.do_not_show_products_without_availability_on_site",
        readonly=False,
    )
