from odoo import api, fields, models, _
from odoo.tools import float_is_zero


class PosPayment(models.Model):
    _inherit = "pos.payment"

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        default=0.0,
        readonly=False,
    )
    foreign_amount = fields.Float(readonly=True, digits=(16, 2))
    foreign_currency_id = fields.Many2one("res.currency", compute="_compute_foreign_currency_id")

    @api.depends()
    def _compute_foreign_currency_id(self):
        for record in self:
            record.foreign_currency_id = record.env.company.currency_foreign_id

    def _export_for_ui(self, payment):
        res = super()._export_for_ui(payment)
        res["foreign_rate"] = payment.foreign_rate
        res["foreign_amount"] = payment.foreign_amount
        return res

    def _create_payment_moves(self):
        """ The function that creates the payment entry was overwritten so that it has the same 
        rate as the invoice/order/payment
        """
        result = self.env['account.move']
        for payment in self:
            order = payment.pos_order_id
            payment_method = payment.payment_method_id
            if payment_method.type == 'pay_later' or float_is_zero(payment.amount, precision_rounding=order.currency_id.rounding):
                continue
            accounting_partner = self.env["res.partner"]._find_accounting_partner(payment.partner_id)
            pos_session = order.session_id
            journal = pos_session.config_id.journal_id
            payment_move = self.env['account.move'].with_context(default_journal_id=journal.id).create({
                'journal_id': journal.id,
                'date': fields.Date.context_today(order, order.date_order),
                'ref': _('Invoice payment for %s (%s) using %s') % (order.name, order.account_move.name, payment_method.name),
                'pos_payment_ids': payment.ids,
                # >> BINAURAL
                'foreign_rate': payment.foreign_rate,
                'foreign_inverse_rate': payment.foreign_rate,
                'manually_set_rate': True,
                # << BINAURAL
            })
            result |= payment_move
            payment.write({'account_move_id': payment_move.id})
            amounts = pos_session._update_amounts({'amount': 0, 'amount_converted': 0}, {'amount': payment.amount}, payment.payment_date)
            credit_line_vals = pos_session._credit_amounts({
                'account_id': accounting_partner.with_company(order.company_id).property_account_receivable_id.id,  # The field being company dependant, we need to make sure the right value is received.
                'partner_id': accounting_partner.id,
                'move_id': payment_move.id,
                'not_foreign_recalculate': True,
                'foreign_debit': abs(payment.foreign_amount)
                if payment.foreign_amount < 0
                else 0,
                'foreign_credit': abs(payment.foreign_amount)
                if payment.foreign_amount > 0
                else 0,
            }, amounts['amount'], amounts['amount_converted'])
            debit_line_vals = pos_session._debit_amounts({
                'account_id': pos_session.company_id.account_default_pos_receivable_account_id.id,
                'move_id': payment_move.id,
                'not_foreign_recalculate': True,
                'foreign_debit': abs(payment.foreign_amount)
                if payment.foreign_amount > 0
                else 0,
                'foreign_credit': abs(payment.foreign_amount)
                if payment.foreign_amount < 0
                else 0,
            }, amounts['amount'], amounts['amount_converted'])
            self.env['account.move.line'].with_context(check_move_validity=False).create([credit_line_vals, debit_line_vals])
            payment_move._post()
        return result
