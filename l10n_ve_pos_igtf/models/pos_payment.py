from odoo import api, fields, models, _
from odoo.tools import float_is_zero
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)


class PosPayment(models.Model):
    _inherit = "pos.payment"

    include_igtf = fields.Boolean()
    igtf_amount = fields.Float()
    foreign_igtf_amount = fields.Float()

    def _export_for_ui(self, payment):
        res = super()._export_for_ui(payment)
        res["include_igtf"] = payment.include_igtf
        res["igtf_amount"] = payment.igtf_amount
        res["foreign_igtf_amount"] = payment.foreign_igtf_amount
        return res

    def _convert_company_to_foreign_amount(self, payment, amount):
        company_currency = payment.company_id.currency_id
        foreign_currency = payment.company_id.foreign_currency_id
        date = payment.payment_date or fields.Date.context_today(payment)

        if not foreign_currency or foreign_currency == company_currency:
            return amount

        converted = company_currency._convert(
            amount,
            foreign_currency,
            payment.company_id,
            date,
        )
        return converted

    def _get_igtf_amounts_for_move(self, payment):
        """Calculate the IGTf amount in company currency and convert it to foreign currency if needed, to be used in the payment move lines."""
        company_igtf_amount = payment.igtf_amount
        foreign_igtf_amount = self._convert_company_to_foreign_amount(
            payment,
            company_igtf_amount,
        )
        return company_igtf_amount, foreign_igtf_amount

    def _get_foreign_debit_credit_vals(self, foreign_amount):
        return {
            "foreign_debit": abs(foreign_amount) if foreign_amount < 0 else 0,
            "foreign_credit": abs(foreign_amount) if foreign_amount > 0 else 0,
        }

    def _get_receivable_account_id(self, accounting_partner, order):
        """Determine the appropriate receivable account to use for the payment move lines, ensuring it is always a standard receivable/payable account to allow proper reconciliation, and log a warning if the configured account is not suitable."""
        return accounting_partner.with_company(order.company_id).property_account_receivable_id.id

    def _create_payment_move(self, payment, order, payment_method, journal):
        """Create the payment move with the appropriate foreign exchange values if the payment is in foreign currency, and link it to the payment."""
        rate, inverse_rate = self._get_payment_rate_values(payment)
        payment_move = (
            self.env["account.move"]
            .with_context(default_journal_id=journal.id)
            .create(
                {
                    "journal_id": journal.id,
                    "date": fields.Date.context_today(order, order.date_order),
                    "ref": _("Invoice payment for %s (%s) using %s")
                    % (order.name, order.account_move.name, payment_method.name),
                    "foreign_rate": rate,
                    "foreign_inverse_rate": inverse_rate,
                    "manually_set_rate": True,
                    "pos_payment_ids": payment.ids,
                }
            )
        )
        payment.write({"account_move_id": payment_move.id})
        return payment_move

    def _build_credit_line_without_igtf(self, pos_session, payment_move, account_id, partner_id, amounts, payment):
        """Build a standard credit line without IGTf tax, with the appropriate foreign debit/credit values if the payment is in foreign currency."""
        foreign_amount = self._get_payment_foreign_amount(payment)
        return pos_session._credit_amounts(
            {
                "account_id": account_id,
                "partner_id": partner_id,
                "move_id": payment_move.id,
                "not_foreign_recalculate": True,
                **self._get_foreign_debit_credit_vals(foreign_amount),
            },
            amounts["amount"],
            amounts["amount_converted"],
        )

    def _build_credit_line_igtf(self, pos_session, payment_move, partner_id, amount_igtf, foreign_amount_igtf):
        """Build a credit line for the IGTf tax. The line will be created on the customer account specified for IGTf in the company configuration, and will have the IGTf amount as credit, with the appropriate foreign debit/credit values if the payment is in foreign currency."""
        return pos_session._credit_amounts(
            {
                "account_id": self.env.company.customer_account_igtf_id.id,
                "partner_id": partner_id,
                "move_id": payment_move.id,
                "not_foreign_recalculate": True,
                **self._get_foreign_debit_credit_vals(foreign_amount_igtf),
            },
            amount_igtf,
            amount_igtf,
        )

    def _build_credit_line_igtf_base(self, pos_session, payment_move, account_id, partner_id, amounts, amount_igtf, foreign_amount_igtf, payment):
        """Build a credit line for the base amount excluding the IGTf tax. The line will be created on the specified account, and will have the base amount as credit, with the appropriate foreign debit/credit values if the payment is in foreign currency."""
        foreign_amount = self._get_payment_foreign_amount(payment)
        amount_without_igtf = foreign_amount - foreign_amount_igtf

        return pos_session._credit_amounts(
            {
                "account_id": account_id,
                "partner_id": partner_id,
                "move_id": payment_move.id,
                "not_foreign_recalculate": True,
                **self._get_foreign_debit_credit_vals(amount_without_igtf),
            },
            amounts["amount"] - amount_igtf,
            amounts["amount_converted"] - amount_igtf,
        )

    def _get_reversed_move_receivable_account_id(self, payment, accounting_partner, order, is_reverse):
        """Determine the appropriate receivable account for the reversed move line in case of split transactions with reversal, ensuring it is always a standard receivable/payable account to allow proper reconciliation, and log a warning if the configured account is not suitable."""
        is_split_transaction = payment.payment_method_id.split_transactions
        valid_types = ("asset_receivable", "liability_payable")

        def _ensure_standard_account(account):
            if account and account.account_type in valid_types:
                return account
            fallback = accounting_partner.with_company(order.company_id).property_account_receivable_id
            if account:
                _logger.warning(
                    "POS payment account '%s' (%s) is not receivable/payable. Falling back to partner receivable '%s'.",
                    account.display_name,
                    account.account_type,
                    fallback.display_name,
                )
            return fallback

        if is_split_transaction and is_reverse:
            account = accounting_partner.with_company(order.company_id).property_account_receivable_id
        elif is_reverse:
            account = (
                payment.payment_method_id.receivable_account_id
                or self.company_id.account_default_pos_receivable_account_id
            )
        else:
            account = self.company_id.account_default_pos_receivable_account_id

        account = _ensure_standard_account(account)
        return account.id, is_split_transaction

    def _build_debit_line(self, pos_session, payment_move, account_id, accounting_partner, is_split_transaction, is_reverse, amounts, payment):
        """In case of split transactions with reversal, the debit line should always be created on the partner's receivable account to properly link the move lines for reconciliation, even if the payment method has a specific receivable account configured. For other cases, it will use the payment method's receivable account or fallback to the default one.
        """
        foreign_amount = self._get_payment_foreign_amount(payment)
        return pos_session._debit_amounts(
            {
                "account_id": account_id,
                "move_id": payment_move.id,
                "partner_id": accounting_partner.id
                if is_split_transaction and is_reverse
                else False,
                "not_foreign_recalculate": True,
                "foreign_debit": abs(foreign_amount)
                if foreign_amount > 0
                else 0,
                "foreign_credit": abs(foreign_amount)
                if foreign_amount < 0
                else 0,
            },
            amounts["amount"],
            amounts["amount_converted"],
        )

    def _create_payment_moves(self, is_reverse=False):
        """Override to create an additional credit line for the IGTf tax when included in the payment, and to handle properly the receivable account in case of split transactions with reversal."""
        result = self.env["account.move"]

        for payment in self:
            order = payment.pos_order_id
            add_credit_line_vals = False
            payment_method = payment.payment_method_id

            accounting_partner = self.env["res.partner"]._find_accounting_partner(
                payment.partner_id
            )
            pos_session = order.session_id
            journal = pos_session.config_id.journal_id
            payment_move = self._create_payment_move(payment, order, payment_method, journal)
            result |= payment_move

            amounts = pos_session._update_amounts(
                {"amount": 0, "amount_converted": 0},
                {"amount": payment.amount},
                payment.payment_date,
            )

            amount_igtf, foreign_amount_igtf = self._get_igtf_amounts_for_move(
                payment,
            )

            receivable_account_id = self._get_receivable_account_id(accounting_partner, order)

            if payment.include_igtf:
                # Keep the original behavior: only add base line when net amount is not exactly zero.
                if not float_is_zero(
                    amounts["amount"] - amount_igtf,
                    precision_rounding=payment.company_id.currency_id.rounding,
                ):
                    add_credit_line_vals = self._build_credit_line_igtf_base(
                        pos_session=pos_session,
                        payment_move=payment_move,
                        account_id=receivable_account_id,
                        partner_id=accounting_partner.id,
                        amounts=amounts,
                        amount_igtf=amount_igtf,
                        foreign_amount_igtf=foreign_amount_igtf,
                        payment=payment,
                    )

                credit_line_vals = self._build_credit_line_igtf(
                    pos_session=pos_session,
                    payment_move=payment_move,
                    partner_id=accounting_partner.id,
                    amount_igtf=amount_igtf,
                    foreign_amount_igtf=foreign_amount_igtf,
                )
            else:
                credit_line_vals = self._build_credit_line_without_igtf(
                    pos_session=pos_session,
                    payment_move=payment_move,
                    account_id=receivable_account_id,
                    partner_id=accounting_partner.id,
                    amounts=amounts,
                    payment=payment,
                )

            reversed_move_receivable_account_id, is_split_transaction = self._get_reversed_move_receivable_account_id(
                payment=payment,
                accounting_partner=accounting_partner,
                order=order,
                is_reverse=is_reverse,
            )

            debit_line_vals = self._build_debit_line(
                pos_session=pos_session,
                payment_move=payment_move,
                account_id=reversed_move_receivable_account_id,
                accounting_partner=accounting_partner,
                is_split_transaction=is_split_transaction,
                is_reverse=is_reverse,
                amounts=amounts,
                payment=payment,
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
