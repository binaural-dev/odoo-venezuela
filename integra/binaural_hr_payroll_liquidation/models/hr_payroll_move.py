from odoo import fields, models


class HrPayrollMove(models.Model):
    _inherit = "hr.payroll.move"

    move_type = fields.Selection(
        selection_add=[
            ("benefits", "Benefits"),
            ("profit_sharing",),
            ("liquidation", "Liquidation"),
        ],
        ondelete={"beneftis": "cascade"},
    )
    benefits_payment = fields.Float()
    advance_of_benefits = fields.Float()
    foreign_advance_of_benefits = fields.Float()
    foreign_benefits_payment = fields.Float()
