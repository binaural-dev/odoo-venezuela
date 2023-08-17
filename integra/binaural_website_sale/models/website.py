from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    do_not_show_products_without_availability_on_site = fields.Boolean(default=False)
