from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class PaymentMobile(models.Model):
    _name = "payment.mobile"
    _description = "Payments Mobile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "id"
    _check_company_auto = True

    def default_alternate_currency(self):
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False

    name = fields.Char(string="Nombre", tracking=True)
    partner_id = fields.Many2one("res.partner", "Client", tracking=True, required=True)
    amount = fields.Monetary(
        tracking=True,
        compute="_compute_amount_total",
    )
    payment_mobile_line = fields.One2many("payment.mobile.line", "payment_mobile_id", tracking=True)
    payment_mobile_methods = fields.One2many(
        "payment.mobile.methods", "payment_mobile_id", string="Payment methods"
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("process", "Procesado"),
            ("cancel", "Cancelado"),
        ],
        default="draft",
        tracking=True,
    )
    seller_id = fields.Many2one("hr.employee", string="Seller", tracking=True, required=True)
    seller_id_user = fields.Many2one("res.users", string="Seller User", tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    proof_payment_id = fields.Many2one("payment.mobile.proof", tracking=True)
    proof_file = fields.Binary(related="proof_payment_id.proof_file", tracking=True)
    proof_name = fields.Char(related="proof_payment_id.name")
    verified_payment = fields.Boolean(default=False, tracking=True)
    is_fiscal = fields.Boolean()

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            line._compute_amount_total()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "payment_mobile_line" in vals:
            for line in self:
                line._compute_amount_total()
        return res

    @api.depends("payment_mobile_line")
    def _compute_amount_total(self):
        self.amount_total()

    def amount_total(self):
        for lines in self:
            if not lines.payment_mobile_line:
                lines.amount = 0
            total = 0
            payments = []
            for line in lines.payment_mobile_line:
                if not line.payment_related.id in payments:
                    total += line.amount_payment_total
                    payments.append(line.payment_related.id)
            lines.amount = total

    def cancel_payment(self):
        for line in self.payment_mobile_line:
            if line.payment_related and line.payment_related.state == "posted":
                line.payment_related.action_draft()
                line.payment_related.action_cancel()
                if self.is_fiscal and line.payment_related.is_retention:
                    retentions = (
                        self.env["account.retention.line"]
                        .sudo()
                        .search([("payment_id", "=", line.payment_related.id)])
                    )
                    if retentions:
                        for retention in retentions:
                            retention.retention_id.action_cancel()

        self.state = "cancel"

    def delete_file(self):
        self.proof_payment_id = False

    def compute_test(self):
        for line in self.payment_mobile_line:
            line._compute_amount()
            line._compute_amount_foreign()
            line._compute_amount_payment_total()
            line._compute_foreign_amount_payment_total()


class PaymentMobileLine(models.Model):
    _name = "payment.mobile.line"
    _description = "Payment Mobile Line"

    def default_alternate_currency(self):
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False

    name = fields.Char()
    payment_mobile_id = fields.Many2one("payment.mobile", string="Associated receipt")
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
        required=True,
    )
    partner_id = fields.Many2one("res.partner", string="Client", related="invoice_id.partner_id")
    transfer_number = fields.Char()

    journal_id = fields.Many2one(
        "account.journal", string="Diario", related="payment_related.journal_id"
    )

    amount = fields.Monetary(
        compute="_compute_amount",
        store=True,
    )
    foreign_amount = fields.Monetary(
        compute="_compute_amount_foreign",
        currency_field="foreign_currency_id",
        store=True,
        digits='Tasa',
    )
    amount_residual = fields.Monetary(
        string="Residual", related="invoice_id.amount_residual", currency_field="currency_id"
    )
    amount_payment_total = fields.Monetary(
        compute="_compute_amount_payment_total",
        store=True,
    )
    foreign_amount_payment_total = fields.Monetary(
        compute="_compute_foreign_amount_payment_total",
        currency_field="foreign_currency_id",
        digits='Tasa',
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    payment_related = fields.Many2one("account.payment", string="Pago Relacionado")

    foreign_currency_id = fields.Many2one(
        "res.currency", string="Moneda/Divisa", default=default_alternate_currency
    )
    foreign_rate = fields.Float(related="payment_related.foreign_rate")

    invoice_number = fields.Char(related="invoice_id.name")
    total_invoice = fields.Monetary(related="invoice_id.amount_total")
    iva = fields.Monetary(related="invoice_id.amount_tax")
    subtotal = fields.Monetary(string="Taxable Base", related="invoice_id.amount_untaxed")

    payment_date = fields.Date(related="payment_related.date")

    use_balance = fields.Boolean()

    memo = fields.Char(related="payment_related.ref")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            line._compute_amount()
            line._compute_amount_foreign()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "payment_related" in vals:
            for line in self:
                line._compute_amount()
                line._compute_amount_foreign()
        return res

    @api.depends("payment_related")
    def _compute_amount_payment_total(self):
        for line in self:
            if line.payment_related.currency_id != line.currency_id:
                line.amount_payment_total = (
                    line.payment_related.amount / line.payment_related.foreign_rate
                    if line.payment_related.foreign_rate != 0
                    else line.payment_related.amount
                )
            else:
                line.amount_payment_total = line.payment_related.amount

    @api.depends("payment_related")
    def _compute_foreign_amount_payment_total(self):
        for line in self:
            if line.payment_related.currency_id != line.foreign_currency_id:
                line.foreign_amount_payment_total = (
                    line.payment_related.amount * line.payment_related.foreign_rate
                )
            else:
                line.foreign_amount_payment_total = line.payment_related.amount

    @api.depends("payment_related")
    def _compute_amount(self):
        for line in self:
            reconcile = self.env["account.partial.reconcile"].search(
                [
                    ("debit_move_id", "in", line.invoice_id.line_ids.ids),
                    ("credit_move_id", "in", line.payment_related.move_id.line_ids.ids),
                ]
            )

            reconcile_payments = line.invoice_id.invoice_payments_widget["content"]

            for rec in reconcile_payments:
                if rec["partial_id"] == reconcile.id:
                    line.amount = rec["amount"]

    @api.depends("payment_related")
    def _compute_amount_foreign(self):
        for line in self:
            reconcile = self.env["account.partial.reconcile"].search(
                [
                    ("debit_move_id", "in", line.invoice_id.line_ids.ids),
                    ("credit_move_id", "in", line.payment_related.move_id.line_ids.ids),
                ]
            )

            reconcile_payments = line.invoice_id.invoice_payments_widget["content"]
            for rec in reconcile_payments:
                if rec["partial_id"] == reconcile.id:
                    if line.payment_related.currency_id != line.foreign_currency_id:
                        line.foreign_amount = rec["amount"] * reconcile.credit_move_id.foreign_rate
                    else:
                        line.foreign_amount = rec["amount"] * reconcile.credit_move_id.foreign_rate # bs
                        if line.foreign_amount > line.foreign_amount_payment_total:
                            line.foreign_amount = line.foreign_amount_payment_total


class PaymentMobileMethods(models.Model):
    _name = "payment.mobile.methods"
    _description = "Payment methods received"
    _rec_name = "journal_id"

    journal_id = fields.Many2one(
        "account.journal",
        string="Payment method",
        required=True,
        related="residual_payment.journal_id",
    )
    amount = fields.Monetary(string="Monto recibido", related="residual_payment.amount")
    amount_compute = fields.Float(string="Monto calculado")
    currency_id = fields.Many2one(
        "res.currency",
        readonly=True,
        related="journal_id.currency_id",
    )
    payment_mobile_id = fields.Many2one("payment.mobile", string="Associated receipt")

    residual_payment = fields.Many2one(
        "account.payment",
    )


class PaymentMobileProof(models.Model):
    _name = "payment.mobile.proof"
    _description = "Proof of payment"

    name = fields.Char(
        required=True,
        help="Make sure that when you finish assigning the name, put the corresponding format (.pdf, .doc, .docx)",
    )
    proof_file = fields.Binary(attachment=True)
