from odoo import api, fields, models, _


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    category = fields.Selection(
        selection_add=[
            ("benefits", "Benefits"),
            ("profit_sharing",),
            ("liquidation", "Liquidation"),
        ],
        ondelete={"benefits": "cascade"},
    )
