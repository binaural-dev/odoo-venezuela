from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    compute_payroll_using = fields.Selection(
        [("base_wage", "Base Wage"), ("foreign_wage", "Foreign Wage")]
    )
