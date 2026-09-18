from odoo import api, fields, models, _
from odoo.tools import formatLang, float_is_zero, float_compare
from odoo.tools.float_utils import float_round
from odoo.exceptions import ValidationError


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

    def _sanitize_payment_move_line_vals(
        self,
        line_vals,
        payment_move,
        accounting_partner,
        fallback_account_id=False,
    ):
        """Normalize account.move.line vals for POS invoice-payment moves.

        This DB enforces `display_type` as NOT NULL and some companies require
        partner on receivable/payable accounts, so we make the vals explicit.
        """
        if not line_vals:
            return line_vals

        vals = dict(line_vals)
        account_id = vals.get("account_id") or fallback_account_id
        if not account_id:
            raise ValidationError(
                _("Customer receivable account is not configured for POS payment posting.")
            )

        vals["account_id"] = account_id
        vals["move_id"] = payment_move.id
        vals["display_type"] = vals.get("display_type") or "product"
        vals["name"] = vals.get("name") or _("PoS invoice payment")

        account_type = self.env["account.account"].browse(account_id).account_type
        if account_type in ("asset_receivable", "liability_payable") and not vals.get("partner_id"):
            vals["partner_id"] = accounting_partner.id

        return vals

    def _get_partner_receivable_account_id(self, order, accounting_partner):
        partner_receivable = accounting_partner.with_company(
            order.company_id
        ).property_account_receivable_id.id
        if not partner_receivable:
            raise ValidationError(
                _("Customer receivable account is not configured for partner '%s'.")
                % accounting_partner.display_name
            )
        return partner_receivable

    def _create_payment_moves(self, is_reverse=False):
        result = self.env["account.move"]
        for payment in self:
            order = payment.pos_order_id
            add_credit_line_vals = False
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
                        "date": fields.Date.context_today(order, order.date_order),
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
            amount_igtf = payment.igtf_amount

            if payment.include_igtf:
                if not (amounts["amount"] - amount_igtf == 0):
                    partner_receivable_account_id = self._get_partner_receivable_account_id(
                        order, accounting_partner
                    )
                    add_credit_line_vals = pos_session._credit_amounts(
                        {
                            "account_id": partner_receivable_account_id,
                            "partner_id": accounting_partner.id,
                            "move_id": payment_move.id,
                        },
                        amounts["amount"] - amount_igtf,
                        amounts["amount_converted"] - amount_igtf,
                    )

                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": self.env.company.customer_account_igtf_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amount_igtf,
                    amount_igtf,
                )
            else:
                partner_receivable_account_id = self._get_partner_receivable_account_id(
                    order, accounting_partner
                )
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": partner_receivable_account_id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amounts["amount"],
                    amounts["amount_converted"],
                )

            is_split_transaction = payment.payment_method_id.split_transactions
            if is_reverse:
                reversed_move_receivable_account_id = (
                    payment.payment_method_id.receivable_account_id.id
                    or self.company_id.account_default_pos_receivable_account_id.id
                )
            else:
                reversed_move_receivable_account_id = (
                    self.company_id.account_default_pos_receivable_account_id.id
                )
            debit_line_vals = pos_session._debit_amounts(
                {
                    "account_id": reversed_move_receivable_account_id,
                    "move_id": payment_move.id,
                    "partner_id": accounting_partner.id
                    if is_split_transaction and is_reverse
                    else False,
                },
                amounts["amount"],
                amounts["amount_converted"],
            )

            credit_fallback_account_id = payment.payment_method_id.receivable_account_id.id
            debit_fallback_account_id = self.company_id.account_default_pos_receivable_account_id.id

            if not debit_line_vals.get("account_id") and not debit_fallback_account_id:
                raise ValidationError(
                    _("Default POS receivable account is not configured for payment posting.")
                )

            credit_line_vals = self._sanitize_payment_move_line_vals(
                credit_line_vals,
                payment_move,
                accounting_partner,
                credit_fallback_account_id,
            )
            debit_line_vals = self._sanitize_payment_move_line_vals(
                debit_line_vals,
                payment_move,
                accounting_partner,
                debit_fallback_account_id,
            )
            add_credit_line_vals = self._sanitize_payment_move_line_vals(
                add_credit_line_vals,
                payment_move,
                accounting_partner,
                credit_fallback_account_id,
            )

            if add_credit_line_vals:
                receivable_line = self.env["account.move.line"].with_context(check_move_validity=False).create(
                    [add_credit_line_vals]
                )
                receivable_line = receivable_line.exists()
                if receivable_line:
                    receivable_line.not_foreign_recalculate = True
                    receivable_line.foreign_credit = abs(payment.foreign_amount - payment.foreign_igtf_amount)
            other_lines = self.env["account.move.line"].with_context(check_move_validity=False).create([credit_line_vals, debit_line_vals])
            other_lines = other_lines.exists()

            credit_lines = other_lines.filtered(lambda line: line.credit > 0)
            debit_lines = other_lines.filtered(lambda line: line.debit > 0)
            if not credit_lines or not debit_lines:
                raise ValidationError(
                    _("POS IGTF payment lines could not be created correctly. Check server logs for details.")
                )

            igtf_or_receivable_line = credit_lines[0]
            debit_line = debit_lines[0]

            # Setear Bs correctos en la línea de débito (CUENTA POR COBRAR POS)
            debit_line.not_foreign_recalculate = True
            debit_line.foreign_debit = abs(payment.foreign_amount)

            # Setear Bs correctos en crédito IGTF o cuenta por cobrar (pago sin IGTF split)
            igtf_or_receivable_line.not_foreign_recalculate = True
            if payment.include_igtf:
                igtf_or_receivable_line.foreign_credit = abs(payment.foreign_igtf_amount)
            else:
                igtf_or_receivable_line.foreign_credit = abs(payment.foreign_amount)

            payment_move._post()
        return result
