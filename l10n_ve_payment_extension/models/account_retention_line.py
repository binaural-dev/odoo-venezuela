from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class AccountRetentionLine(models.Model):
    _name = "account.retention.line"
    _description = "Retention Line"

    check_company = True

    name = fields.Char(
        string="Description", required=True, compute="_compute_name", store=True, readonly=False
    )
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
    date_accounting = fields.Date(related="retention_id.date_accounting", store=True)
    aliquot = fields.Float(digits=(16, 2))
    amount_tax_ret = fields.Float(string="Retained tax", digits=(16, 2))
    base_ret = fields.Float("Retained base", digits=(16, 2))
    imp_ret = fields.Float(string="tax incurred", digits=(16, 2))
    retention_rate = fields.Float(store=True, digits="Tasa")
    move_id = fields.Many2one("account.move", "move", ondelete="cascade", store=True)
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
    code=fields.Char(
        related="payment_concept_id.line_payment_concept_ids.code"
    )
    code_visible=fields.Boolean(
        related='company_id.code_visible')
    economic_activity_id = fields.Many2one(
        "economic.activity",
        ondelete="cascade",
        compute="_compute_economic_activity_id",
        readonly=False,
        store=True,
        index=True,
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

    # foreign currency
    foreign_invoice_amount = fields.Float(
        string="Foreign taxable income", compute="_compute_amounts", store=True, readonly=False
    )
    foreign_invoice_total = fields.Float(string="Foreign total invoiced")
    foreign_iva_amount = fields.Float(string="Foreign IVA")
    foreign_currency_rate = fields.Float(string="Rate")

    @api.depends("retention_id.type_retention", "move_id")
    def _compute_name(self):
        for record in self:
            if record.name:
                continue
            names = {
                "islr": _("ISLR Retention"),
                "iva": _("IVA Retention"),
                "municipal": _("Municipal Retention"),
            }
            type_retention = "islr"
            if record.retention_id.type_retention:
                type_retention = record.retention_id.type_retention
            elif record.move_id:
                if record in record.move_id.retention_iva_line_ids:
                    type_retention = "iva"
                elif record in record.move_id.retention_municipal_line_ids:
                    type_retention = "municipal"

            record.name = names.get(type_retention, _("Retention"))

    @api.depends("retention_id", "move_id")
    def _compute_economic_activity_id(self):
        for line in self:
            if line.economic_activity_id:
                continue
            if line.retention_id and line.retention_id.type_retention == "municipal":
                line.economic_activity_id = line.retention_id.partner_id.economic_activity_id
            if line.move_id and line.id in line.move_id.retention_municipal_line_ids.ids:
                line.economic_activity_id = line.move_id.partner_id.economic_activity_id

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
                # if not record.move_id.partner_id.type_person_id:
                #     raise UserError(_("The partner does not have a type of person"))

                if record.move_id.partner_id.type_person_id.id == line.type_person_id.id:
                    # compare the type_person_id of the partner with the type_person_id of the
                    # payment concept and set the related fields.
                    record.invoice_total = record.move_id.tax_totals["amount_total"]
                    record.foreign_invoice_total = record.move_id.tax_totals["foreign_amount_total"]
                    record.related_pay_from = line.pay_from
                    record.related_percentage_tax_base = line.percentage_tax_base
                    record.related_percentage_fees = line.tariff_id.percentage
                    record.related_amount_subtract_fees = line.tariff_id.amount_subtract
                    record.foreign_currency_rate = record.move_id.foreign_rate

                    if not record.retention_id or record.retention_id.type == "in_invoice":
                        # We don't want this fields to be computed when the retention is
                        # created from a customer invoice since they are filled by the user.
                        record.invoice_amount = record.move_id.tax_totals["amount_untaxed"]
                        record.foreign_invoice_amount = record.move_id.tax_totals[
                            "foreign_amount_untaxed"
                        ]

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

        islr_supplier_retention_lines = self.filtered(
            lambda l: (not l.retention_id and l.payment_concept_id)
            or (l.retention_id.type_retention == "islr" and l.retention_id.type == "in_invoice")
        )
        for record in islr_supplier_retention_lines:
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

    @api.onchange("economic_activity_id", "move_id")
    def onchange_economic_activity_id(self):
        """
        Computes the aliquot of the line when the economic activity is changed for the retentions
        of municipal type.
        """
        municipal_retention_lines_with_economic_activity_and_invoice = self.filtered(
            lambda l: (not l.retention_id or (l.retention_id.type_retention == "municipal"))
            and l.economic_activity_id
            and l.move_id
        )

        for record in municipal_retention_lines_with_economic_activity_and_invoice:
            if not record.retention_id or record.retention_id.type == "in_invoice":
                # We don't want this fields to be computed when the retention is
                # created from a customer invoice since they are filled by the user.
                record.invoice_amount = record.move_id.tax_totals["amount_untaxed"]
                record.foreign_invoice_amount = record.move_id.tax_totals["foreign_amount_untaxed"]

            record.invoice_total = record.move_id.tax_totals["amount_total"]
            record.foreign_invoice_total = record.move_id.tax_totals["foreign_amount_total"]
            record.foreign_currency_rate = record.move_id.foreign_rate

            record.aliquot = record.economic_activity_id.aliquot
            record.retention_amount = record.invoice_amount * record.aliquot / 100
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100

    @api.onchange("invoice_amount", "foreign_invoice_amount", "aliquot")
    def onchange_municipal_invoice_amount(self):
        """
        Computes the retention amount when the invoice amount or the aliquot are changed for the
        retentions of municipal type.
        """
        for record in self.filtered(
            lambda l: (not l.retention_id and l.economic_activity_id)
            or l.retention_id.type_retention == "municipal"
        ):
            record.retention_amount = record.invoice_amount * record.aliquot / 100
            record.foreign_retention_amount = record.foreign_invoice_amount * record.aliquot / 100

    @api.onchange("retention_amount", "invoice_amount")
    def onchange_retention_amount(self):
        """
        Making sure that the foreign retention amount and foreign invoice amount are updated when
        the retention amount or the invoice amount are changed on the retention line of the
        customer retentions.

        This is made to be triggered only when the foreign currency is NOT VEF, as this is the only
        case when the retention amount and the invoice amount are shown on the retention line,
        because the amounts of the retention lines are always shown in VEF.
        """
        if self.env.context.get("noonchange", False):
            return
        for line in self.filtered(
            lambda l: not l.retention_id or l.retention_id.type == "out_invoice"
        ):
            self.env.context = self.with_context(noonchange=True).env.context
            if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
                line.update(
                    {
                        "foreign_invoice_amount": line.invoice_amount
                        * line.move_id.foreign_inverse_rate
                    }
                )
            line.update(
                {
                    "foreign_retention_amount": line.retention_amount
                    * line.move_id.foreign_inverse_rate
                }
            )

    @api.onchange("foreign_retention_amount", "foreign_invoice_amount")
    def onchange_foreign_retention_amount(self):
        """
        Making sure that the retention amount and the invoice amount are updated when the foreign
        retention amount or the foreign invoice amount are changed on the retention line of the
        customer retentions.

        This is made to be triggered only when the foreign currency is VEF, as this is the only
        case when the foreign retention amount and the foreign iva amount are shown on the views of
        the customer retentions, because the amounts of the retention lines are always shown in VEF.
        """
        if self.env.context.get("noonchange", False):
            return
        for line in self.filtered(
            lambda l: not l.retention_id or l.retention_id.type == "out_invoice"
        ):
            if not line.retention_id or line.retention_id.type_retention in ("islr", "municipal"):
                line.update(
                    {
                        "invoice_amount": line.foreign_invoice_amount
                        * (1 / line.move_id.foreign_rate)
                    }
                )
            self.env.context = self.with_context(noonchange=True).env.context
            line.update(
                {
                    "retention_amount": line.foreign_retention_amount
                    * (1 / line.move_id.foreign_rate)
                }
            )

    @api.constrains(
        "retention_amount",
        "invoice_total",
        "foreign_retention_amount",
        "invoice_amount",
        "foreign_invoice_amount",
    )
    def _constraint_amounts(self):
        for record in self:
            if any(
                (
                    record.retention_amount == 0,
                    record.invoice_total == 0,
                    record.foreign_retention_amount == 0,
                    record.invoice_amount == 0,
                    record.foreign_invoice_amount == 0,
                )
            ):
                raise ValidationError(_("You can not create a retention with 0 amount."))

            is_vef_the_base_currency = self.env.company.currency_id == self.env.ref("base.VEF")
            is_client_retention = record.retention_id.type == "out_invoice"
            if (
                is_vef_the_base_currency
                and is_client_retention
                and record.retention_amount > record.move_id.amount_residual
            ):
                raise ValidationError(
                    _(
                        "The total amount of the retention is greater than the residual amount of"
                        " the invoice."
                    )
                )

    def get_invoice_paid_amount_not_related_with_retentions(self):
        """
        Returns the amount paid on the invoice that is not related with the retentions for the ISLR
        supplier retention lines.
        """
        # We need to get the lines without duplicate invoices because the invoice can have more
        # than one retention line.
        lines_without_duplicate_invoices = self.env[self._name]
        for line in self.filtered(
            lambda l: l.retention_id and l.retention_id.type_retention == "islr"
        ):
            if line.move_id in lines_without_duplicate_invoices.mapped("move_id"):
                continue
            lines_without_duplicate_invoices |= line

        for line in lines_without_duplicate_invoices:
            partials = self.env["account.partial.reconcile"].search(
                [
                    (
                        "credit_move_id",
                        "=",
                        line.move_id.line_ids.filtered(
                            lambda l: l.account_id.account_type == "liability_payable"
                            and l.credit > 0
                        )[0].id,
                    )
                ]
            )
            retention_payments = self.env["account.payment"].search(
                [
                    ("move_id.line_ids", "in", partials.mapped("debit_move_id").ids),
                    ("is_retention", "=", True),
                ]
            )
            # The invoice paid amount not related with retentions is the sum of the debit amounts
            # of the partials that are not related with the retention payments.
            invoice_paid_amount_not_related_with_retentions = sum(
                partial.debit_amount_currency
                if partial.debit_currency_id == self.env.ref("base.VEF")
                else partial.debit_amount_currency * partial.debit_move_id.foreign_inverse_rate
                for partial in partials.filtered(
                    lambda p: p.debit_move_id not in retention_payments.mapped("move_id.line_ids")
                )
            )
            return invoice_paid_amount_not_related_with_retentions
