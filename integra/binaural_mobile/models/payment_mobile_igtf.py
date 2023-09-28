from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PaymentMobileIgtf(models.Model):
    _name = "payment.mobile.igtf"
    _description = "Payments Mobile With IGTF"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "id"
    _check_company_auto = True

    name = fields.Char(related='payment_id.name', tracking=True)
    payment_id = fields.Many2one("account.payment", required=True)
    state = fields.Selection(
        [("to_posted", "To Be Posted"), ("posted", "Posted"), ("cancel", "Canceled")],
        default="to_posted",
        tracking=True,
    )
    seller_id = fields.Many2one("hr.employee", tracking=True, required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Client", related="payment_id.partner_id", tracking=True
    )
    journal_id = fields.Many2one("account.journal", related="payment_id.journal_id")
    currency_id = fields.Many2one(
        "res.currency",
        related="payment_id.currency_id",
    )
    amount_igtf = fields.Monetary(
        tracking=True,
    )
    amount = fields.Monetary(related="payment_id.amount")
    payment_mobile_id = fields.Many2one(
        "payment.mobile",
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company,)

    def posted_igtf(self):
        self.state = "posted"

    def cancel_igtf(self):
        self.state = "cancel"
