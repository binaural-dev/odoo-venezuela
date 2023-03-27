from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"

    check_company = True

    name = fields.Char(string="Description", required=True, default="ISLR Retention")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(related="retention_id.state")
    company_currency_id = fields.Many2one(related="retention_id.company_currency_id")
    foreign_currency_id = fields.Many2one(related="retention_id.foreign_currency_id")
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
    retention_rate = fields.Float(store=True, digits="Tasa")
    move_id = fields.Many2one("account.move", "move", ondelete="cascade", store=True)
    # retention_move_id = fields.One2many("account.move", "retention_move_id", string="Retention move")
    is_retention_client = fields.Boolean(default=True)
    display_invoice_number = fields.Char(
        string="Invoice Number", compute="_compute_display_invoice_number", store=True
    )
    invoice_amount = fields.Float(
        string="Taxable income",
        digits="Tasa",
        compute="_compute_amounts",
        store=True,
        readonly=False,
    )
    invoice_total = fields.Float(string="Total invoiced", digits="Tasa", store=True)
    iva_amount = fields.Float(string="IVA", digits=(16, 2))

    retention_amount = fields.Float(
        digits="Tasa", compute="_compute_retention_amount", store=True, readonly=False
    )
    foreign_retention_amount = fields.Float(
        digits="Tasa", compute="_compute_retention_amount", store=True, readonly=False
    )

    payment_concept_id = fields.Many2one(
        "payment.concept", "Payment concept", ondelete="cascade", index=True
    )

    payment_id = fields.Many2one("account.payment", "Payment", index=True)

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
        readonly=False,
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

    check_foreign_currency = fields.Boolean(
        string="Foreign currency",
        compute="_compute_check_foreign_currency",
    )

    # foreign currency
    foreign_invoice_amount = fields.Float(
        string="Foreign taxable income", compute="_compute_amounts", store=True, readonly=False
    )
    foreign_invoice_total = fields.Float(string="Foreign total invoiced")
    foreign_iva_amount = fields.Float(string="Foreign IVA")
    foreign_retention_amount = fields.Float()
    foreign_currency_rate = fields.Float(string="Rate", tracking=True)

    def unlink(self):
        for record in self:
            record.payment_id.unlink()
        return super().unlink()

    @api.onchange("payment_concept_id")
    @api.depends("payment_concept_id", "move_id")
    def _compute_related_fields(self):
        """
        This compute is used to get the related fields from the payment concept of the partner
        to generate the ISLR retention line
        """
        lines_from_islr_retention = self.filtered(
            lambda l: l.payment_concept_id
            and (not l.retention_id or l.retention_id.type_retention == "islr")
        )
        for record in lines_from_islr_retention:
            # Payment concept of the line
            payment_concept = record.payment_concept_id.line_payment_concept_ids
            for line in payment_concept:
                if not record.move_id.partner_id.type_person_id:
                    raise UserError(_("The partner does not have a type of person"))

                if record.move_id.partner_id.type_person_id.id == line.type_person_id.id:
                    # compare the type_person_id of the partner with the type_person_id of the payment concept
                    # and set the related fields
                    record.invoice_total = record.move_id.tax_totals["amount_total"]
                    record.invoice_amount = record.move_id.tax_totals["amount_untaxed"]
                    record.related_pay_from = line.pay_from
                    # record.foreign_iva_amount = record.move_id.tax_totals["amount_total"] - record.move_id.tax_totals["amount_untaxed"]
                    record.related_percentage_tax_base = line.percentage_tax_base
                    record.related_percentage_fees = line.tariff_id.percentage
                    record.related_amount_subtract_fees = line.tariff_id.amount_subtract
                    record.foreign_currency_rate = record.move_id.foreign_rate
                    record.foreign_invoice_amount = record.move_id.tax_totals[
                        "foreign_amount_untaxed"
                    ]
                    record.foreign_invoice_total = record.move_id.tax_totals["foreign_amount_total"]

    @api.depends("invoice_amount", "foreign_invoice_amount")
    def _compute_amounts(self):
        base_currency_is_vef = self.env.company.currency_id == self.env.ref("base.VEF")
        if not base_currency_is_vef:
            for line in self:
                if line.invoice_amount > 0 and line.foreign_invoice_amount > 0:
                    line.invoice_amount = line.foreign_invoice_amount * (
                        1 / line.foreign_currency_rate
                    )

    @api.onchange(
        "invoice_amount",
        "foreign_invoice_amount",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "foreign_currency_rate",
        # "move_id",
    )
    @api.depends(
        "invoice_amount",
        "foreign_invoice_amount",
        "related_percentage_tax_base",
        "related_percentage_fees",
        "related_amount_subtract_fees",
        "foreign_currency_rate",
        "move_id",
    )
    def _compute_retention_amount(self):
        """
         This compute is used to get the retention amount from the payment concept of the partner
        to generate the ISLR retention line.
        """
        base_currency_is_vef = self.env.company.currency_id == self.env.ref("base.VEF")

        lines_from_islr_retention = self.filtered(
            lambda l: not l.retention_id or l.retention_id.type_retention == "islr"
        )
        for record in lines_from_islr_retention:
            foreign_rate = record.move_id.foreign_rate
            if not foreign_rate:
                foreign_rate = 1
            if not base_currency_is_vef:
                record.retention_amount = (
                    record.invoice_amount
                    * (record.related_percentage_tax_base / 100)
                    * (record.related_percentage_fees / 100)
                ) - record.related_amount_subtract_fees / foreign_rate
            else:
                record.retention_amount = (
                    record.invoice_amount
                    * (record.related_percentage_tax_base / 100)
                    * (record.related_percentage_fees / 100)
                ) - record.related_amount_subtract_fees

            record.foreign_retention_amount = (
                record.foreign_invoice_amount
                * (record.related_percentage_tax_base / 100)
                * (record.related_percentage_fees / 100)
            ) - record.related_amount_subtract_fees

    @api.onchange("retention_amount")
    def onchange_retention_amount(self):
        """
        Making sure that the foreign retention amount is updated when the retention amount is
        changed on the retention line of the iva customer retentions.

        This is made to be triggered only when the foreign currency is NOT VEF, as this is the only
        case when the retention amount is shown on the retention line, because the amounts of the
        retention lines are always shown in VEF.
        """
        if self.env.context.get("noonchange", False):
            return
        for line in self.filtered(
            lambda l: (l.retention_id.type_retention, l.retention_id.type) == ("iva", "out_invoice")
        ):
            self.env.context = self.with_context(noonchange=True).env.context
            line.update(
                {
                    "foreign_retention_amount": line.retention_amount
                    * line.move_id.foreign_inverse_rate
                }
            )

    @api.onchange("foreign_retention_amount")
    def onchange_foreign_retention_amount(self):
        """
        Making sure that the retention amount is updated when the foreign retention amount is
        changed on the retention line of the iva customer retentions.

        This is made to be triggered only when the foreign currency is VEF, as this is the only
        case when the foreign retention amount is shown on the view of the iva customer retention,
        because the amounts of the retention lines are always shown in VEF.
        """
        if self.env.context.get("noonchange", False):
            return
        for line in self.filtered(
            lambda l: (l.retention_id.type_retention, l.retention_id.type) == ("iva", "out_invoice")
        ):
            self.env.context = self.with_context(noonchange=True).env.context
            line.update(
                {
                    "retention_amount": line.foreign_retention_amount
                    * (1 / line.move_id.foreign_rate)
                }
            )

    @api.constrains("retention_amount", "invoice_total", "foreign_retention_amount")
    def _constraint_municipality_tax(self):
        for record in self:
            if any(
                (
                    record.retention_amount == 0,
                    record.invoice_total == 0,
                    record.foreign_retention_amount == 0,
                )
            ):
                raise ValidationError(_("You can not create a retention with 0 amount."))

            if record.retention_amount > record.move_id.amount_residual:
                raise ValidationError(
                    _(
                        "The total amount of the retention is greater than the residual amount of"
                        " the invoice."
                    )
                )
