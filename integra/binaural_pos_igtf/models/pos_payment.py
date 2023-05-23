from odoo import api, fields, models, _
from odoo.tools import formatLang, float_is_zero, float_compare


class PosPayment(models.Model):
    _inherit = "pos.payment"

    def _create_payment_moves(self):
        """
        This function is overwritten, because it now sends the igtf account placed in the
        configuration when it receives a payment with the "Apply igtf" check
        """
        result = self.env["account.move"]
        amount_igtf = 0
        all_payments_in_usd = False
        only_one_payment = True if len(self) == 1 else False
        for payment in self:
            if payment.payment_method_id.apply_igtf:
                all_payments_in_usd = True
        for payment in self:
            order = payment.pos_order_id
            amount_igtf = order.igtf_amount
            payment_method = payment.payment_method_id
            if payment_method.type == "pay_later" or float_is_zero(
                payment.amount, precision_rounding=order.currency_id.rounding
            ):
                continue
            accounting_partner = self.env["res.partner"]._find_accounting_partner(
                payment.partner_id
            )
            pos_session = order.session_id
            journal = pos_session.config_id.journal_id
            payment_move = (
                self.env["account.move"]
                .with_context(default_journal_id=journal.id)
                .create(
                    {
                        "journal_id": journal.id,
                        "date": fields.Date.context_today(payment),
                        "ref": _("Invoice payment for %s (%s) using %s")
                        % (order.name, order.account_move.name, payment_method.name),
                        "pos_payment_ids": payment.ids,
                    }
                )
            )
            result |= payment_move
            payment.write({"account_move_id": payment_move.id})
            amounts = pos_session._update_amounts(
                {"amount": 0, "amount_converted": 0},
                {"amount": payment.amount},
                payment.payment_date,
            )
            add_credit_line_vals = False
            is_full_amount = (
                float_compare(
                    amount_igtf,
                    amounts["amount"],
                    precision_rounding=self.env.company.currency_id.rounding,
                )
                == 0
            )
            if (
                is_full_amount
                and not payment.payment_method_id.apply_igtf
                or is_full_amount
                and all_payments_in_usd
                and amount_igtf != 0
            ):
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": self.env.company.customer_account_igtf_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amounts["amount"],
                    amounts["amount_converted"],
                )
            elif not payment.payment_method_id.apply_igtf or (
                only_one_payment and all_payments_in_usd and amount_igtf != 0
            ):
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": accounting_partner.with_company(
                            order.company_id
                        ).property_account_receivable_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amounts["amount"] - amount_igtf,
                    amounts["amount_converted"] - amount_igtf,
                )

                add_credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": self.env.company.customer_account_igtf_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amount_igtf,
                    amount_igtf,
                )
            else:
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": accounting_partner.with_company(
                            order.company_id
                        ).property_account_receivable_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amounts["amount"],
                    amounts["amount_converted"],
                )

            debit_line_vals = pos_session._debit_amounts(
                {
                    "account_id": pos_session.company_id.account_default_pos_receivable_account_id.id,
                    "move_id": payment_move.id,
                },
                amounts["amount"],
                amounts["amount_converted"],
            )
            if add_credit_line_vals:
                self.env["account.move.line"].with_context(check_move_validity=False).create(
                    [add_credit_line_vals]
                )
            self.env["account.move.line"].with_context(check_move_validity=False).create(
                [credit_line_vals, debit_line_vals]
            )
            payment_move._post()
        return result
