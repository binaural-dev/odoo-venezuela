from odoo import Command, _, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _create_payment_line(
        self, session, amount, account=None, message=None, partner=None,
        foreign_currency=None, amount_currency=None,
    ):
        """Settle the IGTF of the payments an invoice is paid with.

        The payment line that core creates for a payment method is the whole
        amount the customer handed over, IGTF included, and settles the
        ``payment_term`` line of the invoice, which only carries the base
        (``pos.order._prepare_account_move_line_data_for_payments``). The IGTF
        goes to its account in its own entry, which also leaves the receivable
        of the customer, and is reconciled together with the payment line and
        the invoice: the receivable ends at zero and the IGTF stays on
        ``customer_account_igtf_id``, as the payment entries of Odoo 19 did.
        """
        lines = super()._create_payment_line(
            session, amount, account, message, partner, foreign_currency, amount_currency
        )
        data = self.env.context.get("l10n_ve_pos_payments_data")
        if not lines or not data or data["session_closing"] or self.type == "pay_later":
            return lines
        entry = self._get_payments_entry(session, amount, foreign_currency)
        if not entry or not entry["metadata"].get("igtf_amount"):
            return lines
        igtf_move = self._create_igtf_move(session, entry, account, partner)
        return lines | igtf_move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )

    def _create_igtf_move(self, session, entry, account, partner):
        """Entry that moves the IGTF of the payments of ``entry`` from the
        receivable of the customer to the IGTF account of the company. A refund
        carries the IGTF with the sign of its payments, so it reverses."""
        self.ensure_one()
        company = session.company_id
        metadata = entry["metadata"]
        payments = metadata["payments"]
        order = payments.pos_order_id[:1]
        config = session.config_id
        currency = session.currency_id
        accounting_partner = self.env["res.partner"]._find_accounting_partner(partner)
        receivable = (
            account
            or accounting_partner.with_company(company).property_account_receivable_id
        )
        igtf = currency.round(metadata["igtf_amount"])
        foreign_igtf = abs(metadata["foreign_igtf_amount"])
        foreign_currency = company.foreign_currency_id
        if foreign_currency:
            foreign_igtf = foreign_currency.round(foreign_igtf)
        move_vals = {
            "move_type": "entry",
            "company_id": company.id,
            "journal_id": config.closing_journal_id.id,
            "date": fields.Date.context_today(order, order.date_order),
            "ref": _(
                "IGTF of %(order)s (%(invoice)s) paid with %(method)s",
                order=order.name,
                invoice=order.account_move.name or "",
                method=self.name,
            ),
            "line_ids": [
                Command.create(
                    {
                        "name": self.name,
                        "account_id": receivable.id,
                        "partner_id": accounting_partner.id,
                        "balance": igtf,
                    }
                ),
                Command.create(
                    {
                        "name": self.name,
                        "account_id": company.customer_account_igtf_id.id,
                        "partner_id": accounting_partner.id,
                        "balance": -igtf,
                    }
                ),
            ],
        }
        move_vals.update(config._get_move_foreign_rate_vals(payments[:1].foreign_rate))
        move = (
            self.env["account.move"]
            .sudo()
            .with_context(skip_invoice_sync=True)
            .create(move_vals)
        )
        for line in move.line_ids:
            line.write(
                {
                    "not_foreign_recalculate": True,
                    "foreign_debit": foreign_igtf if line.debit > 0 else 0.0,
                    "foreign_credit": foreign_igtf if line.credit > 0 else 0.0,
                }
            )
        move._post()
        payments.write({"account_move_id": move.id})
        return move
