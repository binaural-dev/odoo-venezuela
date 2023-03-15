from odoo import api, models, fields, Command, _
from collections import defaultdict
from datetime import datetime
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Retention"
    _check_company_auto = True

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
        states={"draft": [("readonly", False)]},
        help="Descripción del Comprobante",
    )
    code = fields.Char(
        size=32,
        states={"draft": [("readonly", False)]},
        help="Referencia del Comprobante",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancel")],
        index=True,
        default="draft",
        help="Estatus del Comprobante",
    )
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
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
        "Tipo de retención",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Social reason",
        required=True,
        states={"draft": [("readonly", False)]},
        help="Social reason",
    )
    number = fields.Char("Voucher Number")
    correlative = fields.Char(readonly=True)
    date = fields.Date(
        "Fecha Comprobante",
        states={"draft": [("readonly", False)]},
        help="Date of issuance of the withholding voucher by the external party.",
    )
    date_accounting = fields.Date(
        "Fecha Contable",
        states={"draft": [("readonly", False)]},
        help="Date of arrival of the document and date to be used to make the accounting record Keep blank to use current date.",
    )
    retention_line_ids = fields.One2many(
        "account.retention.line",
        "retention_id",
        "retention line",
        states={"draft": [("readonly", False)]},
        help="Retentions",
    )
    payment_ids = fields.Many2many(
        "account.payment",
        "account_payment_retention_rel",
        "retention_id",
        "payment_id",
        "Payments",
        compute="_compute_payments",
        readonly=False,
        store=True,
        help="Payments",
    )

    # amount_base_ret = fields.Float(
    #     compute=amount_ret_all,
    #     string="Base Imponible",
    #     help="Total de la base retenida",
    #     store=True,
    # )
    # amount_imp_ret = fields.Float(compute=amount_ret_all, store=True, string="Total IVA")
    # total_tax_ret = fields.Float(
    #     compute=amount_ret_all,
    #     store=True,
    #     string="IVA retenido",
    #     help="Total del impuesto Retenido",
    # )

    # company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency")

    @api.depends("partner_id")
    def _compute_payments(self):
        for retention in self.filtered(
            lambda r: (r.type_retention, r.state) == ("iva", "draft") and r.partner_id
        ):
            invoices = self.env["account.move"].search(
                [
                    ("partner_id", "=", retention.partner_id.id),
                    ("state", "=", "posted"),
                    ("move_type", "in", ("in_refund", "in_invoice")),
                    ("retention_iva_line_ids", "=", False),
                    ("amount_residual", ">", 0),
                ]
            )
            invoices_with_taxes = invoices.filtered(
                lambda i: any(line.tax_ids[0].amount > 0 for line in i.line_ids)
            )
            if not any(invoices_with_taxes):
                raise UserError(
                    _("There are no invoices with taxes to be retained for the partner.")
                )
            retention.payment_ids.unlink()
            retention.retention_line_ids.unlink()
            Payment = self.env["account.payment"]
            payment_vals = {
                "partner_type": "supplier",
                "partner_id": retention.partner_id.id,
                "payment_type_retention": "iva",
                "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
                "is_retention": True,
                "currency_id": self.env.user.company_id.currency_id.id,
            }

            in_refunds = invoices.filtered(lambda i: i.move_type == "in_refund")
            in_invoices = invoices.filtered(lambda i: i.move_type == "in_invoice")

            def account_move_void_recordset():
                return self.env["account.move"]

            in_refunds_dict = defaultdict(account_move_void_recordset)
            for refund in in_refunds:
                in_refunds_dict[refund.foreign_rate] += refund
            in_invoices_dict = defaultdict(account_move_void_recordset)
            for invoice in in_invoices:
                in_invoices_dict[invoice.foreign_rate] += invoice

            retention_lines_data = []
            payments = Payment
            for refunds in in_refunds_dict.values():
                payment_vals["payment_type"] = "inbound"
                payment = Payment.create(payment_vals)
                payments += payment
                for refund in refunds:
                    retention_lines_data.append(self.compute_retention_lines_data(refund, payment))
            for invoices in in_invoices_dict.values():
                payment_vals["payment_type"] = "outbound"
                payment = Payment.create(payment_vals)
                payments += payment
                for invoice in invoices:
                    retention_lines_data.append(self.compute_retention_lines_data(invoice, payment))
            _logger.warning("Retention lines data %s", retention_lines_data)
            retention_lines = self.env["account.retention.line"].create(
                line for lines in retention_lines_data for line in lines
            )
            payments.compute_retention_amount_from_retention_lines()
            retention.update(
                {
                    "retention_line_ids": retention_lines.ids,
                    "payment_ids": payments.ids,
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            sequence_number = ""
            if vals.get("type_retention") == "iva":
                sequence_number = self.get_sequence_iva_retention().next_by_id()
            elif vals.get("type_retention") == "islr":
                sequence_number = self.get_sequence_islr_retention().next_by_id()
            vals["name"] = sequence_number
            vals["number"] = sequence_number
        return super().create(vals_list)

    @api.model
    def get_sequence_iva_retention(self):
        sequence = self.env["ir.sequence"].search([("code", "=", "retention.iva.control.number")])
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
        sequence = self.env["ir.sequence"].search([("code", "=", "retention.islr.control.number")])
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {
                    "name": "Numero de control retenciones ISLR",
                    "code": "retention.islr.control.number",
                    "padding": 5,
                }
            )
        return sequence

    def action_draft(self):
        self.write({"state": "draft"})
        return True

    def action_post(self):
        today = datetime.now()
        if not self.date_accounting:
            self.date_accounting = str(today)
        if not self.date:
            self.date = str(today)
        if self.type in ["in_invoice", "in_refund", "in_debit"]:
            # REVISAR CUANDO TOQUE EL FLUJO
            self.payment_ids.action_post()
        elif self.type in ["out_invoice", "out_refund", "out_debit"]:
            if not self.number:
                raise UserError(_("Insert a number for the retention"))
            self.payment_ids.action_post()
        return self.write({"state": "emitted"})

    def action_cancel(self):
        for line in self.retention_line_ids:
            if line.move_id and line.move_id.line_ids:
                line.move_id.line_ids.remove_move_reconcile()
            if line.move_id and line.move_id.state != "draft":
                line.move_id.button_cancel()
            if line.retention_id.type_retention in ["iva"]:
                line.move_id.write({"apply_retention_iva": False, "iva_voucher_number": None})
            if line.retention_id.type_retention in ["islr"]:
                line.move_id.write({"apply_retention_islr": False, "islr_voucher_number": None})
            # line.move_id.unlink()
        self.write({"state": "cancel"})
        return True

    @api.model
    def create_retention(self, invoice_id, type_retention: tuple[str, str]):
        """
        Calls the method to create the payment for the retention of the type specified in the
        type_retention parameter.

        Params
        ------
        invoice_id: account.move
            The invoice to which the retention will be applied.
        type_retention: tuple[str, str]
            The type of retention and the type of invoice.

        Returns
        -------
        account.retention
            The retention created.
        """
        if not invoice_id.partner_id.withholding_type_id:
            raise UserError(_("The partner has no withholding type."))

        retention = self.env["account.retention"]
        payment_type = "outbound"
        if type_retention[1] == "in_refund":
            payment_type = "inbound"

        if type_retention[0] == "iva":
            retention = self.create_supplier_iva_retention(invoice_id, payment_type)
        if type_retention[0] == "islr":
            retention = self.create_supplier_islr_retention(invoice_id, payment_type)

        retention.action_post()
        return retention

    @api.model
    def create_supplier_iva_retention(self, invoice_id, payment_type):
        """
        Creates the payment, the retention and the retention lines for the supplier iva retention.

        Params
        ------
        invoice_id: account.move
            The invoice to which the retention will be applied.

        Returns
        -------
        """
        Payment = self.env["account.payment"]
        Retention = self.env["account.retention"]
        payment = Payment.create(
            {
                "payment_type": payment_type,
                "partner_type": "supplier",
                "partner_id": invoice_id.partner_id.id,
                "payment_type_retention": "iva",
                "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
                "is_retention": True,
                "foreign_rate": invoice_id.foreign_rate,
                "currency_id": self.env.user.company_id.currency_id.id,
            }
        )
        retention_lines_data = self.compute_retention_lines_data(invoice_id, payment)
        retention = Retention.create(
            {
                "payment_ids": [Command.link(payment.id)],
                "type_retention": "iva",
                "type": "in_invoice",
                "partner_id": invoice_id.partner_id.id,
                "retention_line_ids": [Command.create(line) for line in retention_lines_data],
            }
        )
        payment.compute_retention_amount_from_retention_lines()
        return retention

    @api.model
    def create_supplier_islr_retention(self, invoice_id, payment_type):
        """
        Creates the payment, the retention and the retention lines for the supplier islr retention.

        Params
        ------
        invoice_id: account.move
            The invoice to which the retention will be applied.

        Returns
        -------
        """
        Payment = self.env["account.payment"]
        Retention = self.env["account.retention"]
        payment = Payment.create(
            {
                "payment_type": payment_type,
                "partner_type": "supplier",
                "partner_id": invoice_id.partner_id.id,
                "payment_type_retention": "islr",
                "retention_line_ids": invoice_id.retention_islr_line_ids,
                "payment_method_id": self.env.ref("account.account_payment_method_manual_in").id,
                "is_retention": True,
                "foreign_rate": invoice_id.foreign_rate,
                "currency_id": self.env.user.company_id.currency_id.id,
            }
        )
        retention = Retention.create(
            {
                "payment_ids": [Command.link(payment.id)],
                "type_retention": "islr",
                "type": "in_invoice",
                "partner_id": invoice_id.partner_id.id,
                "retention_line_ids": invoice_id.retention_islr_line_ids,
            }
        )
        payment.compute_retention_amount_from_retention_lines()
        return retention

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
            taxes = tax_ids.filtered(lambda l: l.tax_group_id.id == tax_group["tax_group_id"])
            if not taxes:
                continue
            tax = taxes[0]
            retention_amount = tax_group["tax_group_amount"] * (withholding_amount / 100)
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
                "retention_amount": retention_amount,
                "foreign_retention_amount": retention_amount * invoice_id.foreign_inverse_rate,
            }
            lines_data.append(line_data)
        return lines_data
