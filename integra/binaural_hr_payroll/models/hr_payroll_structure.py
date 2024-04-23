from odoo import api, fields, models, _


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    category = fields.Selection(
        [
            ("salary", "Salary"),
            ("vacation", "Vacation"),
            ("benefits", "Benefits"),
            ("profit_sharing", "Profit Sharing"),
            ("liquidation", "Liquidation"),
            ("provision", "Provision"),
            ("advance", "Advance"),
        ],
        default="salary",
    )
