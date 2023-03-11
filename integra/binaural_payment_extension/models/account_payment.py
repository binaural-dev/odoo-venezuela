from odoo import models, fields, api, _

class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_retention = fields.Boolean(
        string="Is retention",
        help="Check this box if this payment is a retention",
        default=False,
    )

    payment_type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
        ],
    )

    retention_line_ids = fields.Many2many(
        "account.retention.line",
        string="Retention Lines",
        store=True,
    )

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        domain="[('tax_ids', '!=', False)]",
        string="Invoice Lines",
        store=True,
    )

    retention_ref = fields.Char(
        string="Retention reference",
        store=True,
    )
