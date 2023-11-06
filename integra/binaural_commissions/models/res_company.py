from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.company"

    commission_product_id = fields.Many2one(
        "product.product",
        string="Commission Product",
        default=lambda self: self.env["ir.model.data"]._xmlid_to_res_id(
            "binaural_commissions.product_product_commission_payment"
        ),
    )
    commission_journal_id = fields.Many2one("account.journal", string="Commission Journal")
    commission_invoice_date_field = fields.Selection(
        [
            ("invoice_date", "Invoice Date"),
            ("invoice_reception_date", "Invoice Reception Date"),
        ],
        default="invoice_date",
    )
    compute_commission_when = fields.Selection(
        [
            ("invoice_is_fully_paid", "Invoice paid totally"),
            ("invoice_first_payment", "Invoice first payment"),
        ],
        default="invoice_is_fully_paid",
    )
    commission_payment_through = fields.Selection(
        [
            ("commission_invoice", "Commission Invoice"),
            ("payroll", "Payroll"),
        ],
        default="commission_invoice",
    )
