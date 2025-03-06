from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from ..utils.utils_retention import load_retention_lines


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    company_currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    foreign_currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_foreign_id
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF")
    )

    is_out_invoice = fields.Boolean()
    is_retention = fields.Boolean(string="IVA Retention payment", default=False)
    edit_retention_fields = fields.Boolean(default=True)

    voucher_date = fields.Date(
        "Fecha Comprobante",
        help="Date of issuance of the withholding voucher by the external party.",
    )
    retention_ref = fields.Char(string="Retention reference")

    retention_line_ids = fields.Many2many("account.retention.line")

    @api.depends("payment_type", "company_id", "can_edit_wizard")
    def _compute_available_journal_ids(self):
        """
        Ensure that the supplier retention journals are not selectable for customer payments.
        """
        res = super()._compute_available_journal_ids()
        supplier_retention_journal_ids = (
            self.env.company.iva_supplier_retention_journal_id.id,
            self.env.company.islr_supplier_retention_journal_id.id,
            self.env.company.municipal_supplier_retention_journal_id.id,
        )
        for wizard in self:
            wizard.available_journal_ids = wizard.available_journal_ids.filtered_domain(
                [("id", "not in", supplier_retention_journal_ids)]
            )
        return res

    @api.onchange("is_retention")
    def _onchange_retention(self):
        """
        Sets the journal for iva customer retentions and loads the retention lines from the
        invoices.

        If the payment is not a retention, we clear the retention lines and set the edit_retention
        fields to True, so the user can edit the payment fields.
        """
        if not self.is_retention:
            return {
                "value": {"retention_line_ids": [Command.clear()], "edit_retention_fields": True}
            }
        if self.can_group_payments:
            self.group_payment = False
        self.journal_id = self.env.company.iva_customer_retention_journal_id.id
        self.edit_retention_fields = False
        move_ids = self._context.get("active_ids", [])
        invoices = self.env["account.move"].browse(move_ids)

        lines = self._load_iva_retention_lines(invoices)
        return lines

    def _load_iva_retention_lines(self, invoices):
        """
        Loads the retention lines from the invoices when the retention payment to register is of
        type IVA.

        If any of the invoices selected has a retention line in a draft or emitted retention, we
        raise an error.

        If any of the invoices selected doesn't have any tax line, we raise an error.

        Parameters
        ----------
        invoices : recordset of account.move
            The invoices to load the retention lines from.
        Returns
        -------
        dict
            The onchange values containing the lines to be loaded or the errors.
        """
        invoices_without_taxes = invoices.filtered(
            lambda i: not any(line.tax_ids[0].amount > 0 for line in i.line_ids if line.tax_ids)
        )
        if any(invoices_without_taxes):
            error = _(
                "You can't create a retention payment for the invoices selected because "
                "one or more of them don't have any tax line."
            )
            return {
                "warning": {"title": _("Error"), "message": error},
                "value": {"is_retention": False},
            }

        invoices_with_emitted_retention = invoices.filtered(
            lambda i: any(
                i.retention_iva_line_ids.filtered(lambda l: l.state in ("draft", "emitted"))
            )
        )
        if any(invoices_with_emitted_retention):
            error = _(
                "You can't create a retention payment for the invoices selected because "
                "one or more of them already have an emitted retention."
            )
            return {
                "warning": {"title": _("Error"), "message": error},
                "value": {"is_retention": False},
            }

        retention_lines = []
        for invoice in invoices:
            retention_lines.extend(load_retention_lines(invoice, self.env["account.retention"]))
        return {"value": {"retention_line_ids": retention_lines}}

    @api.onchange("retention_line_ids")
    def _onchange_retention_line_ids(self):
        """
        If the retention lines change, we compute the amount of the payment using their retention
        amounts.

        This is made just for the user to see the amount of the payment before posting it, as we
        compute the amount of the payment from the retention lines in the _init_payments method
        (this is due the fact that it can create multiple payments, if that wasn't the case, this
        onchange would suffice to compute the payment amount).
        """
        if not self.retention_line_ids:
            return
        self.amount = sum(self.retention_line_ids.mapped("retention_amount"))

    def _init_payments(self, to_process, edit_mode=False):
        """
        If the payment is a retention, we add the retention lines to the payment record, compute
        its amount with them, create the retention record and post it. This handles the payment
        post and reconciliation with the invoices.

        Returns
        -------
        recordset of account.payment
            The payments already posted and reconciled with the invoices.
        """
        payments = super()._init_payments(to_process, edit_mode)
        if not self.is_retention:
            return payments
        for payment, vals in zip(payments, to_process):
            payment.is_retention = True
            payment.retention_line_ids = [
                Command.link(line.id)
                for line in self.retention_line_ids
                if line.move_id == vals["to_reconcile"].move_id
            ]
            payment.journal_id = self.env.company.iva_customer_retention_journal_id.id
            payment.compute_retention_amount_from_retention_lines()
            payment.foreign_rate = vals["to_reconcile"].move_id.foreign_rate
            payment.foreign_inverse_rate = vals["to_reconcile"].move_id.foreign_inverse_rate
        retention = self._create_retention(payments)
        retention.action_post()
        return payments

    def _post_payments(self, to_process, edit_mode=False):
        """
        If the payment is a retention, we avoid the post of the payment because we manage that
        in the retention action_post method.
        """
        return super()._post_payments(to_process, edit_mode) if not self.is_retention else None

    def _reconcile_payments(self, to_process, edit_mode=False):
        """
        If the payment is a retention, we avoid the reconciliation of the payment with the invoices
        because we manage that in the retention action_post method.
        """
        if self.is_retention:
            return
        return super()._reconcile_payments(to_process, edit_mode)

    def _create_retention(self, payments):
        """
        Creates the retention record from the payments records.

        Its retention type its iva and its type is out_invoice, as it will always be a customer
        iva retention payment the one that is created through this wizard.

        Parameters
        ----------
        payments : recordset of account.payment
            The payments records that will be linked to the retention.

        Returns
        -------
        recordset of account.retention
            The retention record created.
        """
        retention = self.env["account.retention"].create(
            {
                "name": "Retention IVA",
                "type_retention": "iva",
                "date": self.voucher_date,
                "date_accounting": self.payment_date,
                "partner_id": self.partner_id.id,
                "company_id": self.company_id.id,
                "code": self.retention_ref,
                "number": self.retention_ref,
                "correlative": self.retention_ref,
                "type": "out_invoice",
                "payment_ids": payments.ids,
                "retention_line_ids": self.retention_line_ids.ids,
            }
        )
        return retention
