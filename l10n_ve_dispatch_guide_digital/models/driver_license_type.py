from odoo import fields, models


class DriverLicenseType(models.Model):
    _name = "driver.license.type"
    _description = "Driver License Type"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", help="Short code")
    description = fields.Text(string="Description")
