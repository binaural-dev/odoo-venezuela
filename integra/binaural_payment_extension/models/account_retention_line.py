from odoo import models, fields, api, _


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"

    check_company = True

    name = fields.Char(string="Description", required=True, default="ISLR Retention")
    # currency_id = fields.Many2one(
    #    "res.currency", string="Currency", readonly=True
    # )
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda self: self.env.company
    )
    company_currency_id = fields.Many2one("res.currency", string="Company Currency", readonly=True)
    retention_id = fields.Many2one("account.retention", string="Retention", ondelete="cascade")
    invoice_type = fields.Selection(
        selection=[
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
        ],
    )
    # invoice_number = fields.Char(string="Invoice Number", related="invoice_id.name", store=True)
    aliquot = fields.Float(digits=(16, 2))
    amount_tax_ret = fields.Float(string="Retained tax", digits=(16, 2))
    base_ret = fields.Float("Retained base", digits=(16, 2))
    imp_ret = fields.Float(string="tax incurred", digits=(16, 2))
    retention_rate = fields.Float(store=True, digits=(16, 2))
    move_id = fields.Many2one("account.move", "move", readonly=True, ondelete="cascade")
    is_retention_client = fields.Boolean(default=True)
    display_invoice_number = fields.Char(
        string="Invoice Number", compute="_compute_display_invoice_number", store=True
    )
    invoice_amount = fields.Float(string="Taxable income", digits=(16, 2))
    invoice_total = fields.Float(string="Total invoiced", digits=(16, 2))
    iva_amount = fields.Float(string="IVA", digits=(16, 2))
    retention_amount = fields.Float(digits=(16, 2))

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )

    payment_id = fields.Many2one("account.payment", "Payment", ondelete="cascade", index=True)

    payment_date = fields.Date()

    payment_journal_id = fields.Many2one(
        "account.journal", "Payment journal", ondelete="cascade", index=True
    )

    # foreign currency
    foreign_invoice_amount = fields.Float(string="Foreign taxable income")
    foreign_invoice_total = fields.Float(string="Foreign total invoiced")
    foreign_iva_amount = fields.Float(string="Foreign IVA")
    foreign_retention_amount = fields.Float()
    foreign_currency_rate = fields.Float(string="Rate", tracking=True)
