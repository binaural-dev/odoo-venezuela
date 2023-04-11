from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare
import json


class AccountMove(models.Model):
    _inherit = "account.move"

    outstanding_credits_debits_widget2 = fields.Text(
        compute="_compute_get_outstanding_info_JSON2", groups="account.group_account_invoice"
    )
    invoice_outstanding_credits_debits_widget2 = fields.Text(
        groups="account.group_account_invoice,account.group_account_readonly",
        compute="_compute_payments_widget_to_reconcile_info2",
    )

    def _compute_paymets_widget_to_reconcile_info2(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget2 = json.dumps(False)
            move.invoice_has_outstanding = False

            if (
                move.state != "posted"
                or move.payment_state not in ("not_paid", "partial")
                or not move.is_invoice(include_receipts=True)
            ):
                continue

            pay_term_lines = move.line_ids.filtered(
                lambda line: line.account_id.user_type_id.type in ("receivable", "payable")
            )
            domain = []
            if move.move_type in ("out_invoice", "in_refund"):
                # advance_account = self.env['account.payment.config.advance'].search(
                #     [('active', '=', True), ('advance_type', '=', 'customer')], limit=1)
                advance_account = self.env.company.advance_customer_account_id
                if advance_account:
                    domain = [
                        ("account_id", "=", advance_account.id),
                        ("move_id.state", "=", "posted"),
                        ("partner_id", "=", move.commercial_partner_id.id),
                        ("reconciled", "=", False),
                        "|",
                        ("amount_residual", "!=", 0.0),
                        ("amount_residual_currency", "!=", 0.0),
                        ("credit", ">", 0),
                        ("debit", "=", 0),
                    ]
            else:
                advance_account = self.env.company.advance_supplier_account_id
                if advance_account:
                    domain = [
                        ("account_id", "=", advance_account.id),
                        ("move_id.state", "=", "posted"),
                        ("partner_id", "=", move.commercial_partner_id.id),
                        ("reconciled", "=", False),
                        "|",
                        ("amount_residual", "!=", 0.0),
                        ("amount_residual_currency", "!=", 0.0),
                        ("credit", "=", 0),
                        ("debit", ">", 0),
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
                        "currency": move.currency_id.symbol,
                        "id": line.id,
                        "move_id": line.move_id.id,
                        "position": move.currency_id.position,
                        "digits": [69, move.currency_id.decimal_places],
                        "payment_date": fields.Date.to_string(line.date),
                    }
                )

            if not payments_widget_vals["content"]:
                continue

            move.invoice_outstanding_credits_debits_widget2 = json.dumps(payments_widget_vals)
            move.invoice_has_outstanding = True

    def _compute_get_outstanding_info_JSON2(self):
        self.outstanding_credits_debits_widget2 = json.dumps(False)
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
                self.outstanding_credits_debits_widget2 = json.dumps(info)
                # self.has_outstanding = True

    def js_assign_outstanding_line(self, line_id):
        lines = self.env["account.move.line"].browse(line_id)
        payment = self.env["account.payment"].search([("move_id", "=", lines.move_id.id)], limit=1)
        if payment.is_advance:
            return self._create_advance_payment_moves(line_id)
        return super().js_assign_outstanding_line(line_id)

    def _create_advance_payment_moves(self, line_id):
        lines = self.env["account.move.line"].browse(line_id)
        payment = self.env["account.payment"].search([("move_id", "=", lines.move_id.id)], limit=1)
        account = False

        for line in self.line_ids.filtered(lambda line: line.account_id.account_type in ("asset_receivable", "liability_payable")):
            account = line.account_id.id
        
        if payment.is_advance:
            payment_line_advance = payment.line_ids.filtered(lambda line: line.account_id == payment.destination_account_id)


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
        if move_line_partial.payment_id_advance and move_line_partial.payment_id_advance.is_advance:
            move_line_partial.move_id.cancel_move()

        move_line_partial = self.env["account.move.line"].browse(
            partial_advance_payment.debit_move_id.id
        )
        if move_line_partial.payment_id_advance and move_line_partial.payment_id_advance.is_advance:
            move_line_partial.move_id.cancel_move()
