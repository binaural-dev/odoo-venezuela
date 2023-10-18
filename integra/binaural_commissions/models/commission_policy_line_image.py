from odoo import api, fields, models, _


class CommissionPolicyLineImage(models.Model):
    _name = "commission.policy.line.image"
    _description = "Commission Policy Line Image"

    date_from = fields.Integer(required=True, default=1)
    date_to = fields.Integer(required=True)
    commission = fields.Float(required=True, help="Commission percentage")
    percentage_report = fields.Float(
        "Percentage for Reports", help="Commission percentage of reports"
    )
    not_applied = fields.Boolean(
        "Do not apply to the report", help="Do not apply this restriction to the report"
    )
    # sale_order_line_id = fields.Many2one("sale.order.line", required=True, ondelete="cascade")
