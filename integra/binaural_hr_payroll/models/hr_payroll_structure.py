from odoo import api, fields, models, _


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    category = fields.Selection(
        [
            ("salary", "Salary"),
            ("vacation", "Vacation"),
            ("profit_sharing", "Profit Sharing"),
            ("provision", "Provision"),
            ("advance", "Advance"),
            ("other", "Other"),
        ],
        default="salary",
    )
