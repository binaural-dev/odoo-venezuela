from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_driver = fields.Boolean(string="Is Driver", default=False)
    driver_license_type_id = fields.Many2one(
        comodel_name="driver.license.type",
        string="License Type",
        invisible="not is_driver",
    )
