from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    prefix_vat = fields.Selection(
        [
            ("V", "V"),
            ("E", "E"),
        ],
        default="V",
    )
    vat = fields.Char(string="RIF")
