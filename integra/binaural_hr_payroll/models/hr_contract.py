from odoo import fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    foreign_wage = fields.Monetary()
    foreign_hourly_wage = fields.Monetary()
