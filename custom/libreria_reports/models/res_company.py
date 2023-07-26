from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    store_location_id = fields.Many2one("stock.location", string="Store Location")
