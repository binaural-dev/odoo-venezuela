from odoo import api, fields, models, Command, _
from odoo.tools import float_is_zero
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    outstanding_credits_debits_widget2 = fields.Binary(
        compute="_compute_get_outstanding_info_JSON2"
    )
    invoice_outstanding_credits_debits_widget2 = fields.Binary(
        compute="_compute_payments_widget_to_reconcile_info2",
    )

    def _compute_payments_widget_to_reconcile_info2(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget2 = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids.filtered(
                lambda line: line.account_id.account_type
                in ("asset_receivable", "liability_payable")
            )
            domain = []
            if move.move_type in ("out_invoice", "in_refund"):
                advance_account = self.env.company.advance_customer_account_id
                if advance_account:
                    domain = [
                        ("account_id", "=", advance_account.id),
                        ("move_id.state", "=", "posted"),
                        ("partner_id", "=", move.commercial_partner_id.id),
                        ("reconciled", "=", False),
                        # "|",
                        # ("amount_residual", "!=", 0.0),
                        # ("amount_residual_currency", "!=", 0.0),
                        # ("credit", ">", 0),
                        # ("debit", "=", 0),
                    ]
            else:
                advance_account = self.env.company.advance_supplier_account_id
                if advance_account:
                    domain = [
                        ("account_id", "=", advance_account.id),
                        ("move_id.state", "=", "posted"),
                        ("partner_id", "=", move.commercial_partner_id.id),
                        ("reconciled", "=", False),
                        # "|",
                        # ("amount_residual", "!=", 0.0),
                        # ("amount_residual_currency", "!=", 0.0),
                        # ("credit", "=", 0),
                        # ("debit", ">", 0),
                    ]
            payments_widget_vals = {"outstanding": True, "content": [], "move_id": move.id}

            if move.is_inbound():
                domain.append(("balance", "<", 0.0))
                payments_widget_vals["title"] = _("Outstanding credits")
            else:
                domain.append(("balance", ">", 0.0))
                payments_widget_vals["title"] = _("Outstanding debits")

            for line in self.env["account.move.line"].search(domain):
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                else:
                    # Different foreign currencies.
                    amount = move.company_currency_id._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )

                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals["content"].append(
                    {
                        "journal_name": line.ref or line.move_id.name,
                        "amount": amount,
                        # "currency": move.currency_id.symbol,
                        "id": line.id,
                        "move_id": line.move_id.id,
                        "position": move.currency_id.position,
                        "digits": [69, move.currency_id.decimal_places],
                        "payment_date": fields.Date.to_string(line.date),
                    }
                )

            if not payments_widget_vals["content"]:
                continue

            move.invoice_outstanding_credits_debits_widget2 = payments_widget_vals
            move.invoice_has_outstanding = True

    def _compute_get_outstanding_info_JSON2(self):
        self.outstanding_credits_debits_widget2 = False
        if self.payment_state in ["not_paid", "in_payment", "partial"]:
            domain = [
                (
                    "partner_id",
                    "=",
                    self.env["res.partner"]._find_accounting_partner(self.partner_id).id,
                ),
                ("move_id.state", "=", "posted"),
                "|",
                "&",
                ("amount_residual_currency", "!=", 0.0),
                ("currency_id", "!=", None),
                "&",
                ("amount_residual_currency", "=", 0.0),
                "&",
                ("currency_id", "=", None),
                ("amount_residual", "!=", 0.0),
            ]
            if self.move_type in ("out_invoice", "in_refund"):
                advance_account = self.env.company.advance_customer_account_id
                if advance_account:
                    domain.extend([("account_id", "=", advance_account.id)])
                domain.extend([("credit", ">", 0), ("debit", "=", 0)])

                type_payment = _("Anticipos")
            else:
                advance_account = self.env.company.advance_supplier_account_id
                if advance_account:
                    domain.extend([("account_id", "=", advance_account.id)])
                domain.extend([("credit", "=", 0), ("debit", ">", 0)])
                type_payment = _("Anticipos")
            info = {"title": "", "outstanding": True, "content": [], "invoice_id": self.id}
            if advance_account:
                lines = self.env["account.move.line"].search(domain)
            else:
                lines = []
            currency_id = self.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == self.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        currency = line.company_id.currency_id
                        amount_to_show = currency._convert(
                            abs(line.amount_residual),
                            self.currency_id,
                            self.company_id,
                            line.date or fields.Date.today(),
                        )
                    if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                        continue
                    if line.ref:
                        title = "%s : %s" % (line.move_id.name, line.ref)
                    else:
                        title = line.move_id.name
                    info["content"].append(
                        {
                            "journal_name": line.ref or line.move_id.name,
                            "title": title,
                            "amount": amount_to_show,
                            "currency": currency_id.symbol,
                            "id": line.id,
                            "position": currency_id.position,
                            "digits": [69, self.currency_id.decimal_places],
                        }
                    )
                info["title"] = type_payment
                self.outstanding_credits_debits_widget2 = info
                self.has_outstanding = True

    def js_assign_outstanding_line(self, line_id):
        lines = self.env["account.move.line"].browse(line_id)
        payment = self.env["account.payment"].search([("move_id", "=", lines.move_id.id)], limit=1)
        if payment.is_advance_payment:
            return self._create_advance_payment_moves(line_id)
        return super().js_assign_outstanding_line(line_id)

    def _create_advance_payment_moves(self, line_id):
        lines = self.env["account.move.line"].browse(line_id)
        payment = self.env["account.payment"].search([("move_id", "=", lines.move_id.id)], limit=1)
        account = False

        for line in self.line_ids.filtered(
            lambda line: line.account_id.account_type in ("asset_receivable", "liability_payable")
        ):
            account = line.account_id.id

        if payment.is_advance_payment:
            payment_line_advance = payment.line_ids.filtered(
                lambda line: line.account_id == payment.destination_account_id
            )
            min_amount = 0
            if -payment_line_advance[0].amount_residual < self.amount_residual:
                min_amount = -payment_line_advance[0].amount_residual
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
            if self.move_type in ["out_invoice", "in_refund"]:
                line_vals = [Command.create(
                    {
                        "name": "CUENTA POR COBRAR CLIENTE",
                        "account_id": account,  # cuenta de la factura, CXC
                        "partner_id": self.partner_id.id,
                        "credit": amount_to_show,
                        "debit": 0.0,
                        # 'foreign_currency_rate': payment.foreign_currency_rate,
                        "payment_id_advance": payment.id,
                        "reconciled": False,
                    }
                ), Command.create(
                    {
                        "name": "ANTICIPO/CLIENTE",
                        "account_id": payment.destination_account_id.id,  # cuenta de la factura, CXC
                        "partner_id": self.partner_id.id,
                        "debit": amount_to_show,
                        "credit": 0.0,
                        # 'foreign_currency_rate': payment.foreign_currency_rate,
                        "payment_id_advance": payment.id,
                        "reconciled": False,
                    }
                )]
            else:
                line_vals = [Command.create(
                    {
                        "name": "CUENTA POR PAGAR PROVEEDOR",
                        "account_id": account,  # cuenta de la factura, CXC
                        "partner_id": self.partner_id.id,
                        "credit": 0.0,
                        "debit": amount_to_show,
                        # 'foreign_currency_rate': payment.foreign_currency_rate,
                        "payment_id_advance": payment.id,
                        "reconciled": False,
                    }
                ), Command.create(
                    {
                        "name": "ANTICIPO/PROVEEDOR",
                        "account_id": payment.destination_account_id.id,  # cuenta de la factura, CXC
                        "partner_id": self.partner_id.id,
                        "debit": 0.0,
                        "credit": amount_to_show,
                        # 'foreign_currency_rate': payment.foreign_currency_rate,
                        "payment_id_advance": payment.id,
                        "reconciled": False,
                    }
                )]
            move = self.env["account.move"].create(
                {
                    "name": self.name + " - " + payment.name,
                    "date": self.date,
                    "journal_id": payment.journal_id.id if payment.journal_id else 1,
                    "state": "draft",
                    "line_ids": line_vals,
                    "company_id": self.company_id.id,
                }
            )
            move.action_post()
            account_move_line = False
            for line in move.line_ids:
                if line.name in ('ANTICIPO/CLIENTE', 'ANTICIPO/PROVEEDOR'):
                    account_move_line = line.id
            lines2 = self.env["account.move.line"].browse(account_move_line)
            lines += lines2
            lines.reconcile()

            cta_fv = False

            for cf in move.line_ids:
                    if cf.name in ('CUENTA POR COBRAR CLIENTE', 'CUENTA POR PAGAR PROVEEDOR'):
                        cta_fv = cf.id
            lines3 = self.env['account.move.line'].browse(cta_fv)
            lines3 += self.line_ids.filtered(lambda line: line.account_id == lines3[0].account_id and not line.reconciled)
            return lines3.reconcile()

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
        if move_line_partial.payment_id_advance and move_line_partial.payment_id_advance.is_advance_payment:
            move_line_partial.move_id.cancel_move()

        move_line_partial = self.env["account.move.line"].browse(
            partial_advance_payment.debit_move_id.id
        )
        if move_line_partial.payment_id_advance and move_line_partial.payment_id_advance.is_advance_payment:
            move_line_partial.move_id.cancel_move()
