import logging

from odoo.exceptions import UserError
from odoo import fields, models, Command, _
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    outstanding_credits_debits_widget_advance_payment = fields.Binary(
        compute="_compute_get_outstanding_info_JSON_advance_payment",
    )
    invoice_outstanding_credits_debits_widget_advance_payment = fields.Binary(
        compute="_compute_payments_widget_to_reconcile_info_advance_payment",
    )

    def _get_advance_payment_domain(self, advance_account, move_type):
        balance_operator = "<" if move_type == "out_invoice" else ">"
        return [
            ("account_id", "=", advance_account.id),
            ("move_id.state", "=", "posted"),
            ("partner_id", "=", self.commercial_partner_id.id),
            ("reconciled", "=", False),
            ("balance", balance_operator, 0.0),
        ]

    def _compute_payments_widget_to_reconcile_info_advance_payment(self):
        """Compute the data to display the 'reconcile' button in the invoice form view
        this widget is used to display the advance payment of the customer/supplier in the invoice

        depending on the type of the invoice, we either display the outstanding debit or the outstanding credit
        """
        for move in self:
            move.invoice_outstanding_credits_debits_widget_advance_payment = False
            move.invoice_has_outstanding = False

            if (
                move.state != "posted"
                or move.payment_state not in ("not_paid", "partial")
                or not move.is_invoice(include_receipts=True)
            ):
                continue

            if move.move_type in ("out_invoice", "in_refund"):
                advance_account = self.env.company.advance_customer_account_id
            else:
                advance_account = self.env.company.advance_supplier_account_id

            if not advance_account:
                raise UserError(
                    _(
                        "You must configure the advance customer account and the advance supplier account in the company settings"
                    )
                )

            payments_widget_vals = {
                "outstanding": True,
                "move_id": move.id,
                "title": _("Outstanding credits") if move.is_inbound() else _("Outstanding debits"),
                "content": [
                    {
                        "journal_name": line.ref or line.move_id.name,
                        "amount": (
                            abs(line.amount_residual_currency)
                            if line.currency_id == move.currency_id
                            else move.company_currency_id._convert(
                                abs(line.amount_residual),
                                move.currency_id,
                                move.company_id,
                                line.date,
                            )
                        ),
                        "id": line.id,
                        "move_id": line.move_id.id,
                        "position": move.currency_id.position,
                        "digits": [69, move.currency_id.decimal_places],
                        "payment_date": fields.Date.to_string(line.date),
                    }
                    for line in self.env["account.move.line"].search(
                        self._get_advance_payment_domain(advance_account, move.move_type)
                    )
                    if not move.currency_id.is_zero(
                        abs(line.amount_residual_currency)
                        if line.currency_id == move.currency_id
                        else move.company_currency_id._convert(
                            abs(line.amount_residual),
                            move.currency_id,
                            move.company_id,
                            line.date,
                        )
                    )
                ],
            }

            if not payments_widget_vals["content"]:
                continue

            move.invoice_outstanding_credits_debits_widget_advance_payment = payments_widget_vals
            move.invoice_has_outstanding = True

    def _find_invoice_lines(self, account_id, credit, debit):
        """
        Find invoice lines for the given account_id, credit and debit amount

        this method is used to find the invoice lines for the advance payment of the customer/supplier in the invoice

        Args:
            account_id (int): the account_id to search for invoice lines
            credit (float): the credit amount to search for invoice lines
            debit (float): the debit amount to search for invoice lines

        Returns:
            lines: the invoice lines found for the given account_id, credit and debit amount
        """
        domain = [
            (
                "partner_id",
                "=",
                self.env["res.partner"]._find_accounting_partner(self.partner_id).id,
            ),
            ("move_id.state", "=", "posted"),
        ]

        if account_id:
            domain.append(("account_id", "=", account_id))

        if credit > 0 and debit == 0:
            domain.append(("credit", ">", 0))
        elif credit == 0 and debit > 0:
            domain.append(("debit", ">", 0))

        lines = self.env["account.move.line"].search(domain)

        return lines

    def _get_amount_to_show(self, line):
        """
        Get the amount to show for the given line.

        this method is used to get the amount to show for the advance payment of the customer/supplier in the invoice.

        Args:
            line (account.move.line): the line to get the amount to show.

        Returns:
            float: the amount to show for the given line.
        """
        if line.currency_id and line.currency_id == self.currency_id:
            return abs(line.amount_residual_currency)

        currency = line.company_id.currency_id
        amount_to_show = currency._convert(
            abs(line.amount_residual),
            self.currency_id,
            self.company_id,
            line.date or fields.Date.today(),
        )

        return amount_to_show

    def _get_info_content(self, lines):
        """
        Get the info content for the given lines to show in the widget of the invoice.

        this method is used to get the info content for the advance payment of the customer/supplier in the invoice.

        Args:
            lines (account.move.line): the lines to get the info content.

        Returns:
            list: the info content for the given lines to show in the widget of the invoice.
        """
        content = []

        for line in lines:
            amount_to_show = self._get_amount_to_show(line)

            if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                continue

            if line.ref:
                title = "%s : %s" % (line.move_id.name, line.ref)
            else:
                title = line.move_id.name

            content.append(
                {
                    "journal_name": line.ref or line.move_id.name,
                    "title": title,
                    "amount": amount_to_show,
                    "currency": self.currency_id.symbol,
                    "id": line.id,
                    "position": self.currency_id.position,
                    "digits": [69, self.currency_id.decimal_places],
                }
            )

        return content

    def _compute_get_outstanding_info_JSON_advance_payment(self):
        """
        Compute the outstanding info JSON for the advance payment of the customer/supplier in the invoice to show in the widget of the invoice.

        this method used the method _get_info_content to get the info content for the advance payment of the customer/supplier in the invoice
        to show in the widget of the invoice.
        """
        outstanding_credits_debits_widget_advance_payment = False
        has_outstanding = False

        if self.payment_state in ["not_paid", "in_payment", "partial"]:
            if self.move_type in ("out_invoice", "in_refund"):
                account_id = self.env.company.advance_customer_account_id.id
                type_payment = _("Advance Payments")
                credit = 1
                debit = 0
            else:
                account_id = self.env.company.advance_supplier_account_id.id
                type_payment = _("Advance Payments")
                credit = 0
                debit = 1

            lines = self._find_invoice_lines(account_id, credit, debit)

            info = {
                "title": type_payment,
                "outstanding": True,
                "content": self._get_info_content(lines),
                "invoice_id": self.id,
            }

            if lines:
                outstanding_credits_debits_widget_advance_payment = info
                has_outstanding = True

        self.outstanding_credits_debits_widget_advance_payment = (
            outstanding_credits_debits_widget_advance_payment
        )
        self.has_outstanding = has_outstanding

    def js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        lines = self.env["account.move.line"].browse(line_id)
        payment = self.env["account.payment"].search([("move_id", "=", lines.move_id.id)], limit=1)

        if payment.is_advance_payment:
            return self._create_advance_payment_moves(line_id)

        return super().js_assign_outstanding_line(line_id)

    def get_line_vals(self, move_type, account, amount_to_show, payment):
        if move_type in ["out_invoice", "in_refund"]:
            credit = True
            name_1 = "CUENTA POR COBRAR CLIENTE"
            name_2 = "ANTICIPO/CLIENTE"
            account_2 = (
                payment.destination_account_id.id
                if payment
                else self.env.company.advance_customer_account_id.id
            )
        else:
            credit = False
            name_1 = "CUENTA POR PAGAR PROVEEDOR"
            name_2 = "ANTICIPO/PROVEEDOR"
            account_2 = (
                payment.destination_account_id.id
                if payment
                else self.env.company.advance_supplier_account_id.id
            )

        return [
            Command.create(
                {
                    "name": name_1,
                    "account_id": account,
                    "partner_id": self.partner_id.id,
                    "credit" if credit else "debit": amount_to_show,
                    "debit" if credit else "credit": 0.0,
                    "payment_id_advance": payment.id,
                    "foreign_rate": payment.foreign_rate,
                    "reconciled": False,
                }
            ),
            Command.create(
                {
                    "name": name_2,
                    "account_id": account_2,
                    "partner_id": self.partner_id.id,
                    "debit" if credit else "credit": amount_to_show,
                    "credit" if credit else "debit": 0.0,
                    "payment_id_advance": payment.id,
                    "foreign_rate": payment.foreign_rate,
                    "reconciled": False,
                }
            ),
        ]

    def _create_advance_payment_moves(self, line_id):
        lines = self.env["account.move.line"].browse(line_id)
        payment = self.env["account.payment"].search([("move_id", "=", lines.move_id.id)], limit=1)
        account = False
        amount_to_show = 0

        for line in self.line_ids.filtered(
            lambda line: line.account_id.account_type in ("asset_receivable", "liability_payable")
        ):
            account = line.account_id.id

        if payment.is_advance_payment:
            payment_line_advance = payment.line_ids.filtered(
                lambda line: line.account_id == payment.destination_account_id
            )
            min_amount = 0
            if -payment_line_advance.amount_residual < self.amount_residual:
                min_amount = -payment_line_advance.amount_residual
            else:
                min_amount = self.amount_residual
            if payment.currency_id and payment.currency_id == self.currency_id:
                amount_to_show = abs(min_amount)
                self.currency_id.round(amount_to_show)
            else:
                currency = payment.company_id.currency_id
                amount_to_show = currency._convert(
                    abs(min_amount),
                    self.currency_id,
                    self.company_id,
                    payment.date or fields.Date.today(),
                )

        line_vals = self.get_line_vals(self.move_type, account, amount_to_show, payment)
        move = self._create_payment_move(line_vals, payment)

        account_move_lines = [
            line.id for line in move.line_ids if line.account_id == lines.account_id
        ]
        lines += self.env["account.move.line"].browse(account_move_lines)
        lines.reconcile()

        cta_fv_lines = [
            line.id
            for line in move.line_ids
            if line.account_id.account_type in ("asset_receivable", "liability_payable")
        ]
        cta_fv = self.env["account.move.line"].browse(cta_fv_lines)

        lines_to_reconcile = cta_fv + self.line_ids.filtered(
            lambda line: line.account_id == cta_fv[0].account_id and not line.reconciled
        )
        lines_to_reconcile.reconcile()

        return lines_to_reconcile.ids

    def _create_payment_move(self, line_vals, payment):
        move = self.env["account.move"].create(
            {
                "name": self.name + " - " + payment.name if payment.name else self.name,
                "date": self.date,
                "journal_id": payment.journal_id.id if payment.journal_id else 1,
                "state": "draft",
                "line_ids": line_vals,
                "foreign_currency_id": payment.foreign_currency_id.id,
                "foreign_rate": payment.foreign_rate,
                "company_id": self.company_id.id,
            }
        )
        move.action_post()
        return move

    def js_remove_outstanding_partial(self, partial_id):
        """Called by the 'payment' widget to remove a reconciled entry to the present invoice.

        :param partial_id: The id of an existing partial reconciled with the current invoice.
        """

        self.js_remove_outstanding_advance_payment(partial_id)
        return super().js_remove_outstanding_partial(partial_id)

    def js_remove_outstanding_advance_payment(self, partial_id):
        """Remove the given partial reconciliation from the current invoice.

        :param partial_id: The id of an existing partial reconciled with the current invoice.

        """

        partial_advance_payment = self.env["account.partial.reconcile"].browse(partial_id)

        move_line_partial = self.env["account.move.line"].browse(
            partial_advance_payment.credit_move_id.id
        )
        if (
            move_line_partial.payment_id_advance
            and move_line_partial.payment_id_advance.is_advance_payment
        ):
            move_line_partial.move_id.button_cancel()

        move_line_partial = self.env["account.move.line"].browse(
            partial_advance_payment.debit_move_id.id
        )
        if (
            move_line_partial.payment_id_advance
            and move_line_partial.payment_id_advance.is_advance_payment
        ):
            move_line_partial.move_id.button_cancel()
