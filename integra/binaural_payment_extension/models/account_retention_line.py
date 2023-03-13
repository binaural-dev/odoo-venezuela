from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


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
    foreign_retention_amount = fields.Float(digits=(16, 2))

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )

    payment_id = fields.Many2one("account.payment", "Payment", ondelete="cascade", index=True)

    payment_date = fields.Date(related="payment_id.date", store=True)

    payment_journal_id = fields.Many2one(
        "account.journal",
        "Payment journal",
        ondelete="cascade",
        index=True,
        related="payment_id.journal_id",
    )

    related_pay_from = fields.Float(
        string="Pays from",
        compute="_compute_related_fields",
        store=True,
    )

    related_percentage_tax_base = fields.Float(
        string="% tax base",
        compute="_compute_related_fields",
        store=True,
    )

    related_percentage_fees = fields.Float(
        string="% tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    related_amount_subtract_fees = fields.Float(
        string="Amount subtract tariffs",
        compute="_compute_related_fields",
        store=True,
    )

    # foreign currency
    foreign_invoice_amount = fields.Float(string="Foreign taxable income")
    foreign_invoice_total = fields.Float(string="Foreign total invoiced")
    foreign_iva_amount = fields.Float(string="Foreign IVA")
    foreign_retention_amount = fields.Float()
    foreign_currency_rate = fields.Float(string="Rate", tracking=True)

    @api.onchange("payment_concept_id")
    @api.depends("payment_concept_id", "move_id")
    def _compute_related_fields(self):
        for record in self:
            payment_concept = record.payment_concept_id.line_payment_concept_ids
            for line in payment_concept:
                if record.move_id.partner_id.type_person_id.id == line.type_person_id.id:
                    record.invoice_total = record.move_id.tax_totals["amount_total"]
                    record.invoice_amount = record.move_id.tax_totals["amount_untaxed"]
                    record.related_pay_from = line.pay_from
                    record.related_percentage_tax_base = line.percentage_tax_base
                    record.related_percentage_fees = line.tariff_id.percentage
                    record.related_amount_subtract_fees = line.tariff_id.amount_subtract
                    record.foreign_currency_rate = record.move_id.foreign_rate
                    record.foreign_invoice_amount = record.move_id.tax_totals[
                        "foreign_amount_untaxed"
                    ]
                    record.foreign_invoice_total = record.move_id.tax_totals["foreign_amount_total"]

                    record.retention_amount = (
                        (record.invoice_amount * record.related_percentage_tax_base / 100)
                        * record.related_percentage_fees
                        / 100
                    )

                    record.foreign_retention_amount = (
                        (record.foreign_invoice_amount * record.related_percentage_tax_base / 100)
                        * record.related_percentage_fees
                        / 100
                    )
