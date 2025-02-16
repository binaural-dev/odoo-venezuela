from odoo import api, models, fields, Command, _
from datetime import datetime
from odoo.exceptions import UserError, ValidationError
from ..utils.utils_retention import load_retention_lines, search_invoices_with_taxes
from collections import defaultdict
import json
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Retention"
    _check_company_auto = True

    company_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
    )
    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_foreign_id.id,
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF"),
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(
        "Description",
        size=64,
        help="Description of the withholding voucher",
    )
    code = fields.Char(
        size=32,
        help="Code of the withholding voucher",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancelled")],
        index=True,
        default="draft",
        help="Status of the withholding voucher",
    )
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        required=True,
    )
    type = fields.Selection(
        [
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
            ("out_contingence", "Out contingence"),
            ("in_contingence", "In contingence"),
        ],
        "Type retention",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Social reason",
        required=True,
        help="Social reason",
    )
    number = fields.Char("Voucher Number")
    correlative = fields.Char(readonly=True)
    date = fields.Date(
        "Voucher Date",
        help="Date of issuance of the withholding voucher by the external party.",
    )
    date_accounting = fields.Date(
        "Accounting Date",
        help=(
            "Date of arrival of the document and date to be used to make the accounting record."
            " Keep blank to use current date."
        ),
    )
    allowed_lines_move_ids = fields.Many2many(
        "account.move",
        compute="_compute_allowed_lines_move_ids",
        help=(
            "Technical field to store the allowed move types for the ISLR retention lines. This is"
            " used to filter the moves that can be selected in the ISLR retention lines."
        ),
    )

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "retention_id",
        "retention line",
        help="Retentions",
    )

    code_visible = fields.Boolean(related="company_id.code_visible")

    payment_ids = fields.One2many(
        "account.payment",
        "retention_id",
        help="Payments",
    )

    total_invoice_amount = fields.Float(
        string="Taxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    total_iva_amount = fields.Float(
        string="Total IVA", compute="_compute_totals", store=True
    )
    total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )

    foreign_total_invoice_amount = fields.Float(
        string="Foreign StateTaxable Income",
        compute="_compute_totals",
        help="Taxable Income Total",
        store=True,
    )
    foreign_total_iva_amount = fields.Float(
        string="Foreign Total IVA", compute="_compute_totals", store=True
    )
    foreign_total_retention_amount = fields.Float(
        compute="_compute_totals",
        store=True,
        help="Retained Amount Total",
    )
    original_lines_per_invoice_counter = fields.Char(
        help=(
            "Technical field to store the quantity of retention lines per invoice before the user"
            " changes them. This is used to know if the user has deleted the retention lines when"
            " the invoice is changed, in order to delete all the other lines of the same invoice"
            " that the one that just has been deleted."
        )
    )

    @api.depends("type", "partner_id")
    def _compute_allowed_lines_move_ids(self):
        """
        Computes the allowed move types for the moves of the retention lines.

        If the retention is of type "in_invoice", the allowed move types are "in_invoice" and
        "in_refund". If the retention is of type "out_invoice", the allowed move types are
        "out_invoice" and "out_refund".

        This is used to filter the moves that can be selected in the retention lines for each type
        of retention (ISLR and municipal).
        """
        for retention in self:
            allowed_types = (
                ("in_invoice", "in_refund")
                if retention.type == "in_invoice"
                else ("out_invoice", "out_refund")
            )

            domain = [
                ("company_id", "=", self.env.company.id),
                ("state", "=", "posted"),
                ("partner_id", "=", retention.partner_id.id),
                ("move_type", "in", allowed_types),
            ]

            retention.allowed_lines_move_ids = self.env["account.move"].search(domain)

    @api.depends(
        "retention_line_ids.invoice_amount",
        "retention_line_ids.iva_amount",
        "retention_line_ids.retention_amount",
        "retention_line_ids.foreign_invoice_amount",
        "retention_line_ids.foreign_iva_amount",
        "retention_line_ids.foreign_retention_amount",
    )
    def _compute_totals(self):
        for retention in self:
            retention.total_invoice_amount = 0
            retention.total_iva_amount = 0
            retention.total_retention_amount = 0
            retention.foreign_total_invoice_amount = 0
            retention.foreign_total_iva_amount = 0
            retention.foreign_total_retention_amount = 0

            for line in retention.retention_line_ids:
                if line.move_id.move_type in ("in_refund", "out_refund"):
                    retention.total_invoice_amount -= float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount -= float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount -= float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount -= float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount -= float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount -= float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                else:
                    retention.total_invoice_amount += float_round(
                        line.invoice_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_iva_amount += float_round(
                        line.iva_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.total_retention_amount += float_round(
                        line.retention_amount,
                        precision_digits=retention.company_currency_id.decimal_places,
                    )
                    retention.foreign_total_invoice_amount += float_round(
                        line.foreign_invoice_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_iva_amount += float_round(
                        line.foreign_iva_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )
                    retention.foreign_total_retention_amount += float_round(
                        line.foreign_retention_amount,
                        precision_digits=retention.foreign_currency_id.decimal_places,
                    )

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """
        Load retention lines from invoices with taxes when the partner changes for IVA retentions
        that are not posted.
        """
        self._validate_retention_journals()
        for retention in self.filtered(
            lambda r: (r.state, r.type_retention) == ("draft", "iva") and r.partner_id
        ):
            if retention.type == "in_invoice":
                result = retention._load_retention_lines_for_iva_supplier_retention()
            else:
                result = retention._load_retention_lines_for_iva_customer_retention()
            return result

    def _load_retention_lines_for_iva_supplier_retention(self):
        self.ensure_one()
        self.date_accounting = fields.Date.today()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("in_refund", "in_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda l: l.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the supplier.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _load_retention_lines_for_iva_customer_retention(self):
        self.ensure_one()
        search_domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ("out_refund", "out_invoice")),
            ("amount_residual", ">", 0),
        ]
        invoices_with_taxes = search_invoices_with_taxes(
            self.env["account.move"], search_domain
        ).filtered(
            lambda i: not any(
                i.retention_iva_line_ids.filtered(
                    lambda l: l.state in ("draft", "emitted")
                )
            )
        )
        if not any(invoices_with_taxes):
            raise UserError(
                _("There are no invoices with taxes to be retained for the customer.")
            )
        self.clear_retention()
        lines = load_retention_lines(invoices_with_taxes, self.env["account.retention"])

        lines_per_invoice_counter = defaultdict(int)
        for line in lines:
            lines_per_invoice_counter[str(line[2]["move_id"])] += 1

        return {
            "value": {
                "retention_line_ids": lines,
                "original_lines_per_invoice_counter": json.dumps(
                    lines_per_invoice_counter
                ),
            }
        }

    def _validate_retention_journals(self):
        """
        Validate that the company has the journals configured for the retention type.
        """
        for retention in self:
            # IVA
            if (retention.type_retention, retention.type) == (
                "iva",
                "in_invoice",
            ) and not self.env.company.iva_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier IVA retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "iva",
                "out_invoice",
            ) and not self.env.company.iva_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer IVA retention journal configured."
                    )
                )
            # ISLR
            if (retention.type_retention, retention.type) == (
                "islr",
                "in_invoice",
            ) and not self.env.company.islr_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier ISLR retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "islr",
                "out_invoice",
            ) and not self.env.company.islr_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer ISLR retention journal configured."
                    )
                )
            # Municipal
            if (retention.type_retention, retention.type) == (
                "municipal",
                "in_invoice",
            ) and not self.env.company.municipal_supplier_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a supplier municipal retention journal configured."
                    )
                )
            if (retention.type_retention, retention.type) == (
                "municipal",
                "out_invoice",
            ) and not self.env.company.municipal_customer_retention_journal_id:
                raise UserError(
                    _(
                        "The company must have a customer municipal retention journal configured."
                    )
                )

    def clear_retention(self):
        """
        Clear retention lines and payments.
        """
        self.ensure_one()
        self.update(
            {
                "retention_line_ids": (
                    Command.clear()
                    if any(
                        isinstance(id, models.NewId)
                        for id in self.retention_line_ids.ids
                    )
                    else False
                ),
            }
        )

    @api.onchange("retention_line_ids")
    def onchange_retention_line_ids(self):
        """
        On the IVA supplier retention when a line is deleted, delete all the others lines that have
        the same invoice.
        """
        for retention in self.filtered(
            lambda r: (r.type_retention, r.state) == ("iva", "draft") and r.partner_id
        ):
            original_lines_per_invoice_counter = json.loads(
                retention.original_lines_per_invoice_counter
            )
            lines_per_invoice_counter = defaultdict(int)
            for line in retention.retention_line_ids:
                lines_per_invoice_counter[str(line.move_id.id)] += 1

            for line in retention.retention_line_ids:
                if (
                    line.move_id.id
                    and lines_per_invoice_counter[str(line.move_id.id)]
                    != original_lines_per_invoice_counter[str(line.move_id.id)]
                ):
                    retention.retention_line_ids -= line

            return {
                "value": {
                    "original_lines_per_invoice_counter": json.dumps(
                        lines_per_invoice_counter
                    )
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._create_payments_from_retention_lines()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get("retention_line_ids", False):
            self._create_payments_from_retention_lines()
        return res

    def unlink(self):
        for record in self:
            if record.state == "emitted":
                raise ValidationError(
                    _(
                        "You cannot delete a hold linked to a posted entry. It is necessary to cancel the retention before being deleted"
                    )
                )
        return super().unlink()

    def _create_payments_from_retention_lines(self):
        """
        Create the payments from the retention lines for an IVA retention.

        When there are retention lines without payments, this method will create a payment for each
        set of retention lines that have the same invoice.
        """
        for retention in self:
            if any(retention.payment_ids) or retention.type_retention != "iva":
                continue
            payment_vals = {
                "retention_id": retention.id,
                "partner_id": retention.partner_id.id,
                "payment_type_retention": "iva",
                "is_retention": True,
                "currency_id": self.env.user.company_id.currency_id.id,
            }

            def account_retention_line_empty_recordset():
                return self.env["account.retention.line"]

            if retention.type == "in_invoice":
                self._create_payments_for_iva_supplier(
                    payment_vals, account_retention_line_empty_recordset
                )
            if retention.type == "out_invoice":
                self._create_payments_for_iva_customer(
                    payment_vals, account_retention_line_empty_recordset
                )

    def _create_payments_for_iva_supplier(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        Rate = self.env["res.currency.rate"]
        payment_vals["partner_type"] = "supplier"
        payment_vals[
            "journal_id"
        ] = self.env.company.iva_supplier_retention_journal_id.id
        in_refund_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "in_refund"
        )
        in_invoice_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "in_invoice"
        )

        in_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        in_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in in_refund_lines:
            in_refunds_dict[line.move_id] += line
        for line in in_invoice_lines:
            in_invoices_dict[line.move_id] += line

        for lines in in_refunds_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_in").id,
            )
            payment_vals["payment_type"] = "inbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in in_invoices_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_out").id,
            )
            payment_vals["payment_type"] = "outbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def _create_payments_for_iva_customer(
        self, payment_vals, account_retention_line_empty_recordset
    ):
        Payment = self.env["account.payment"]
        Rate = self.env["res.currency.rate"]
        payment_vals["partner_type"] = "customer"
        payment_vals[
            "journal_id"
        ] = self.env.company.iva_customer_retention_journal_id.id
        out_refund_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "out_refund"
        )
        out_invoice_lines = self.retention_line_ids.filtered(
            lambda l: l.move_id.move_type == "out_invoice"
        )

        out_refunds_dict = defaultdict(account_retention_line_empty_recordset)
        out_invoices_dict = defaultdict(account_retention_line_empty_recordset)

        for line in out_refund_lines:
            out_refunds_dict[line.move_id] += line
        for line in out_invoice_lines:
            out_invoices_dict[line.move_id] += line

        for lines in out_refunds_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_out").id,
            )
            payment_vals["payment_type"] = "outbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()
        for lines in out_invoices_dict.values():
            payment_vals["payment_method_id"] = (
                self.env.ref("account.account_payment_method_manual_in").id,
            )
            payment_vals["payment_type"] = "inbound"
            payment_vals["foreign_rate"] = lines[0].foreign_currency_rate
            payment = Payment.create(payment_vals)
            payment.update(
                {
                    "foreign_inverse_rate": Rate.compute_inverse_rate(
                        payment.foreign_rate
                    )
                }
            )
            lines.write({"payment_id": payment.id})
            payment.compute_retention_amount_from_retention_lines()

    def action_draft(self):
        self.write({"state": "draft"})

    def action_post(self):
        today = datetime.now()
        for retention in self:
            if (
                retention.type in ["out_invoice", "out_refund", "out_debit"]
                and not retention.number
            ):
                raise UserError(_("Insert a number for the retention"))
            if not retention.date_accounting:
                retention.date_accounting = today
            if not retention.date:
                retention.date = today

            move_ids = retention.mapped("retention_line_ids.move_id")
            self.set_voucher_number_in_invoice(move_ids, retention)

            if not retention.payment_ids:
                payments = retention.create_payment_from_retention_form()
                retention.payment_ids = payments.ids

            if retention.type in ["in_invoice", "in_refund", "in_debit"]:
                retention._set_sequence()
                self.set_voucher_number_in_invoice(move_ids, retention)

        self.payment_ids.write({"date": self.date_accounting})
        self._reconcile_all_payments()
        self.write({"state": "emitted"})

    def set_voucher_number_in_invoice(self, move, retention):
        if retention.type_retention == "iva":
            move.write({"iva_voucher_number": retention.number})
        elif retention.type_retention == "islr":
            move.write({"islr_voucher_number": retention.number})
        elif retention.type_retention == "municipal":
            move.write({"municipal_voucher_number": retention.number})

    def action_print_municipal_retention_xlsx(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/get_xlsx_municipal_retention?&retention_id={self.id}",
            "target": "self",
        }

    def _set_sequence(self):
        for retention in self.filtered(lambda r: not r.number):
            sequence_number = ""
            if retention.type_retention == "iva":
                sequence_number = retention.get_sequence_iva_retention().next_by_id()
            elif retention.type_retention == "islr":
                sequence_number = retention.get_sequence_islr_retention().next_by_id()
            else:
                sequence_number = (
                    retention.get_sequence_municipal_retention().next_by_id()
                )
            correlative = f"{retention.date_accounting.year}{retention.date_accounting.month:02d}{sequence_number}"
            retention.name = correlative
            retention.number = correlative

    @api.model
    def get_sequence_iva_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.iva.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones IVA",
                    "code": "retention.iva.control.number",
                    "padding": 5,
                }
            )
        return sequence

    @api.model
    def get_sequence_islr_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.islr.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones ISLR",
                    "code": "retention.islr.control.number",
                    "padding": 5,
                }
            )
        return sequence

    def get_sequence_municipal_retention(self):
        sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "retention.municipal.control.number"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones Municipal",
                    "code": "retention.iva.control.number",
                    "padding": 5,
                }
            )
        return sequence

    def clear_islr_retention_number(self):
        for line in self.retention_line_ids:
            if line.move_id.islr_voucher_number:
                line.move_id.islr_voucher_number = False

    def action_cancel(self):
        self.payment_ids.mapped("move_id.line_ids").remove_move_reconcile()
        self.payment_ids.action_cancel()
        self.write({"state": "cancel"})
        self.clear_islr_retention_number()

    def create_payment_from_retention_form(self):
        """
        Create the corresponding payments for the retention based on the fields of the retention.

        This is meant to create the payment for the ISLR and municipal retentions and it is
        triggered on the action_post method of the retention if it still doesn't have payments at
        that point.

        Returns
        -------
        account.payment recordset
            The payments created for the retention.
        """
        self.ensure_one()
        Payment = self.env["account.payment"]
        journals = {
            ("islr", "in_invoice"): self.env.company.islr_supplier_retention_journal_id,
            (
                "islr",
                "out_invoice",
            ): self.env.company.islr_customer_retention_journal_id,
            (
                "municipal",
                "in_invoice",
            ): self.env.company.municipal_supplier_retention_journal_id,
            (
                "municipal",
                "out_invoice",
            ): self.env.company.municipal_customer_retention_journal_id,
        }
        journal_id = journals[(self.type_retention, self.type)].id

        if self.type_retention == "islr":
            self._validate_islr_retention_fields()

        payment_type = "outbound" if self.type == "in_invoice" else "inbound"
        partner_type = "supplier" if self.type == "in_invoice" else "customer"
        payment_vals = []

        for line in self.retention_line_ids:
            if line.move_id.move_type == "in_refund":
                payment_type = "inbound" if self.type == "in_invoice" else "outbound"
            if line.move_id.move_type == "out_refund":
                payment_type = "outbound" if self.type == "out_invoice" else "inbound"

            payment_method_ref = (
                "account.account_payment_method_manual_in"
                if payment_type == "inbound"
                else "account.account_payment_method_manual_out"
            )

            payment_vals.append(
                {
                    "state": "draft",
                    "payment_type": payment_type,
                    "partner_type": partner_type,
                    "partner_id": line.move_id.partner_id.id,
                    "journal_id": journal_id,
                    "payment_type_retention": self.type_retention,
                    "payment_method_id": self.env.ref(payment_method_ref).id,
                    "is_retention": True,
                    "foreign_rate": line.move_id.foreign_rate,
                    "foreign_inverse_rate": line.move_id.foreign_inverse_rate,
                    "retention_line_ids": line,
                    "currency_id": self.env.user.company_id.currency_id.id,
                }
            )

        # payments = Payment.create(payment_vals)
        payments = self.env["account.payment"]
        for vals in payment_vals:
            payments += Payment.create(vals)
        payments.compute_retention_amount_from_retention_lines()

        return payments

    def _validate_islr_retention_fields(self):
        """
        Validates the partner has a type person and all the retention lines have a payment concept.
        """
        self.ensure_one()
        if not self.partner_id.type_person_id:
            raise UserError(_("Select a type person"))
        if not any(self.retention_line_ids.filtered(lambda l: l.payment_concept_id)):
            raise UserError(_("Select a payment concept"))

    def _reconcile_all_payments(self):
        """
        Reconcile all payments of the retention with the invoice of the lines corresponding to the
        payment.
        """
        for payment in self.mapped("payment_ids"):
            payment.action_post()
            if payment.partner_type == "supplier":
                self._reconcile_supplier_payment(payment)
            if payment.partner_type == "customer":
                self._reconcile_customer_payment(payment)

    def _reconcile_supplier_payment(self, payment):
        if payment.payment_type == "outbound":
            line_to_reconcile = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == "liability_payable"
                and l.debit > 0
            )[0]
            payment.retention_line_ids.move_id.js_assign_outstanding_line(
                line_to_reconcile.id
            )
        elif payment.payment_type == "inbound":
            line_to_reconcile = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == "liability_payable"
                and l.credit > 0
            )[0]
            payment.retention_line_ids.move_id.js_assign_outstanding_line(
                line_to_reconcile.id
            )

    def _reconcile_customer_payment(self, payment):
        if payment.payment_type == "outbound":
            line_to_reconcile = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable"
                and l.debit > 0
            )[0]
            payment.retention_line_ids.move_id.js_assign_outstanding_line(
                line_to_reconcile.id
            )
        elif payment.payment_type == "inbound":
            line_to_reconcile = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable"
                and l.credit > 0
            )[0]
            payment.retention_line_ids.move_id.js_assign_outstanding_line(
                line_to_reconcile.id
            )

    @api.model
    def compute_retention_lines_data(self, invoice_id, payment=None):
        """
        Computes the retention lines data for the given invoice.

        Params
        ------
        invoice_id: account.move
            The invoice for which the retention lines are computed.
        type_retention: tuple[str,str]
            The type of retention and the type of invoice.
        payment: account.payment
            The payment for which the retention lines are computed.

        Returns
        -------
        list[dict]
            The retention lines data.
        """
        tax_ids = invoice_id.invoice_line_ids.filtered(
            lambda l: l.tax_ids and l.tax_ids[0].amount > 0
        ).mapped("tax_ids")
        if not any(tax_ids):
            raise UserError(_("The invoice %s has no tax."), invoice_id.number)

        withholding_amount = invoice_id.partner_id.withholding_type_id.value
        lines_data = []
        subtotals_name = invoice_id.tax_totals["subtotals"][0]["name"]
        tax_groups = zip(
            invoice_id.tax_totals["groups_by_subtotal"][subtotals_name],
            invoice_id.tax_totals["groups_by_foreign_subtotal"][subtotals_name],
        )
        for tax_group, foreign_tax_group in tax_groups:
            taxes = tax_ids.filtered(
                lambda l: l.tax_group_id.id == tax_group["tax_group_id"]
            )
            if not taxes:
                continue
            tax = taxes[0]
            retention_amount = tax_group["tax_group_amount"] * (
                withholding_amount / 100
            )
            retention_amount = float_round(
                retention_amount,
                precision_digits=invoice_id.company_currency_id.decimal_places,
            )
            line_data = {
                "name": _("Iva Retention"),
                "invoice_type": invoice_id.move_type,
                "move_id": invoice_id.id,
                "payment_id": payment.id if payment else None,
                "aliquot": tax.amount,
                "iva_amount": tax_group["tax_group_amount"],
                "invoice_total": invoice_id.tax_totals["amount_total"],
                "related_percentage_tax_base": withholding_amount,
                "invoice_amount": tax_group["tax_group_base_amount"],
                "foreign_currency_rate": invoice_id.foreign_rate,
                "foreign_invoice_amount": foreign_tax_group["tax_group_base_amount"],
                "foreign_iva_amount": foreign_tax_group["tax_group_amount"],
                "foreign_invoice_total": invoice_id.tax_totals["foreign_amount_total"],
            }
            if invoice_id.move_type == "out_invoice":
                line_data["retention_amount"] = 0.0
                line_data["foreign_retention_amount"] = 0.0
            else:
                line_data["retention_amount"] = retention_amount
                line_data["foreign_retention_amount"] = float_round(
                    (line_data["foreign_iva_amount"] * (withholding_amount / 100)),
                    precision_digits=invoice_id.foreign_currency_id.decimal_places,
                )
            lines_data.append(line_data)
        return lines_data

    def get_signature(self):
        config = self.env["signature.config"].search(
            [("active", "=", True), ("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if config and config.signature:
            return config.signature.decode()
        else:
            return False
