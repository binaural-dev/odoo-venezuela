from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    do_not_show_products_without_availability_on_site = fields.Boolean(
        related="website_id.do_not_show_products_without_availability_on_site",
        readonly=False,
    )
    
    budget_send = fields.Boolean(
        related='company_id.budget_send',
        readonly=False,
    )

    people_not_being_able_to_see_prices = fields.Boolean(
        related="website_id.people_not_being_able_to_see_prices",
        readonly=False,
    )

    people_not_being_able_to_see_available = fields.Boolean(
        related="website_id.people_not_being_able_to_see_available",
        readonly=False,
    )
