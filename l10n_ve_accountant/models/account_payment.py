from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    destination_account_id = fields.Many2one(
        "account.account",
        domain="[('account_type', 'in', ('asset_receivable', 'liability_payable', 'asset_current', 'liability_current'))]",
    )
    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.foreign_currency_id.id or False

    foreign_currency_id = fields.Many2one(
        "res.currency", default=default_alternate_currency
    )

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        store=True,
        readonly=False,
    )

    concept = fields.Char()
    is_foreign_currency = fields.Boolean(
        compute="_compute_is_foreign_currency",
        store=True,
    )

    block_change_partner_after_post = fields.Boolean(default=False, copy=False)

    other_rate = fields.Float(
        compute="_compute_other_rate",
        digits="Tasa",
        store=True,
        readonly=False,
        help="This field is shown when the payment is different from the company currency and the company foreign currency. Show the rate of the currency of the payment. NOTE: This field is not the same as the foreign_rate field.",
    )
    other_rate_inverse = fields.Float(
        compute="_compute_other_rate",
        digits=(16, 15),
        store=True,
        readonly=False,
        help="This field is shown when the payment is different from the company currency and the company foreign currency. Show the inverse rate of the currency of the payment. NOTE: This field is not the same as the foreign_inverse_rate field.",
    )
    custom_rate_currency_name = fields.Char(compute="_compute_rate_currency_name")
    company_currency_symbol = fields.Char(related="company_id.currency_id.symbol")

    foreign_amount = fields.Monetary('foreign_amount',currency_field="foreign_currency_id",  compute="_compute_foreign_amount", store=True, readonly=False)

    def _prepare_move_lines_per_type(self, write_off_line_vals=None, force_balance=None):
        """
        Same as the core method (account.payment), except the liquidity line is
        converted to company currency using the l10n_ve_conversion_date context key
        (the invoice date when the payment is not indexed) instead of always using
        the payment date. The wizard sets this context key when creating payments
        (see account_payment_register._create_payments); no field is persisted.
        Duplicated instead of temporarily reassigning self.date, since that would
        trigger a real write() on a stored field and cascade recomputes.
        """
        self.ensure_one()
        conversion_date = self.env.context.get('l10n_ve_conversion_date')
        
        if not conversion_date:
            return super()._prepare_move_lines_per_type(
                write_off_line_vals=write_off_line_vals, force_balance=force_balance
            )

        if not self.outstanding_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %(payment_method)s payment method in the %(journal)s journal.",
                payment_method=self.payment_method_line_id.name, journal=self.journal_id.display_name))

        line_name = ''.join(x[1] for x in self._get_aml_default_display_name_list() if x[1])

        write_off_lines = write_off_line_vals or []
        write_off_amount_currency = sum(x['amount_currency'] for x in write_off_lines)
        write_off_balance = sum(x['balance'] for x in write_off_lines)

        withholding_lines = self._prepare_move_withholding_lines({})
        withholding_amount_currency = sum(x['amount_currency'] for x in withholding_lines)
        withholding_balance = sum(x['balance'] for x in withholding_lines)

        if withholding_lines and write_off_lines:
            write_off_lines = []
            write_off_amount_currency = 0.0
            write_off_balance = 0.0

        if self.payment_type == 'inbound':
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            liquidity_amount_currency = -self.amount
        else:
            liquidity_amount_currency = 0.0

        if not write_off_line_vals and force_balance is not None:
            sign = 1 if liquidity_amount_currency > 0 else -1
            liquidity_balance = sign * abs(force_balance)
        else:
            liquidity_balance = self.currency_id._convert(
                liquidity_amount_currency,
                self.company_id.currency_id,
                self.company_id,
                conversion_date,
            )
        liquidity_amount_currency -= withholding_amount_currency
        liquidity_balance -= withholding_balance

        liquidity_lines = self._prepare_move_liquidity_lines({
            'name': line_name,
            'balance': liquidity_balance,
            'amount_currency': liquidity_amount_currency,
        })

        counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency - withholding_amount_currency
        counterpart_balance = -liquidity_balance - write_off_balance - withholding_balance
        counterpart_lines = self._prepare_move_counterpart_lines({
            'name': line_name,
            'balance': counterpart_balance,
            'amount_currency': counterpart_amount_currency,
        })

        return {
            'liquidity_lines': liquidity_lines,
            'counterpart_lines': counterpart_lines,
            'write_off_lines': write_off_lines,
            'withholding_lines': withholding_lines,
        }

    @api.depends("amount", "currency_id","date")
    def _compute_foreign_amount(self):
        for payment in self:
            if payment.date and payment.currency_id != payment.foreign_currency_id:
                payment.foreign_amount = payment.currency_id._convert(
                    payment.amount,
                    payment.foreign_currency_id,
                    payment.company_id,
                    payment.date 
                )
            else:
                payment.foreign_amount = 0.0



    @api.depends("company_id", "currency_id")
    def _compute_rate_currency_name(self):
        for payment in self:
            if (
                 payment.currency_id == payment.company_id.currency_id
                 or payment.currency_id == payment.company_id.foreign_currency_id
             ):
                payment.custom_rate_currency_name = payment.company_id.foreign_currency_id.name
            else:
                payment.custom_rate_currency_name = payment.currency_id.name

    

    @api.depends("currency_id", "company_id")
    def _compute_is_foreign_currency(self):
        for payment in self:
            payment.is_foreign_currency = (
                payment.currency_id == payment.company_id.foreign_currency_id
            )

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override the create method to set the rate of the payment to its move.
        """
        payments = super().create(vals_list)
        for payment in payments.with_context(skip_account_move_synchronization=True):
            payment.move_id.write(
                {
                    "foreign_rate": payment.foreign_rate,
                    "foreign_inverse_rate": payment.foreign_inverse_rate,
                }
            )
        return payments

    def _synchronize_to_moves(self, changed_fields):
        """
        Override the _syncrhonize_to_moves method to set the rate of the payment to its move.
        """
        res = super()._synchronize_to_moves(changed_fields)
        if not (
            "foreign_rate" in changed_fields or "foreign_inverse_rate" in changed_fields
        ):
            return
        for payment in self.with_context(skip_account_move_synchronization=True):
            payment.move_id.write(
                {
                    "foreign_rate": payment.foreign_rate,
                    "foreign_inverse_rate": payment.foreign_inverse_rate,
                }
            )
        return res

    @api.depends("date", "currency_id")
    def _compute_rate(self):
        """
        Compute the rate of the payment using the compute_rate method of the res.currency.rate model.

        foreign_rate/foreign_inverse_rate are stored+readonly=False, so the wizard's
        create() call can set them explicitly with the indexation-aware rate. But
        being @api.depends("date", "currency_id") means ANY later write to those
        fields (e.g. a manual date correction) silently recomputes and overwrites
        that value with today's rate, discarding the invoice-date rate for
        non-indexed payments. Honor l10n_ve_conversion_date here too so a recompute
        never reverts what the wizard set.
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            conversion_date = self.env.context.get('l10n_ve_conversion_date') or payment.date or fields.Date.today()
            rate_values = Rate.compute_rate(
                payment.foreign_currency_id.id, conversion_date
            )
            payment.update(rate_values)

    @api.depends("date", "currency_id")
    def _compute_other_rate(self):
        """
        Compute the visual rate of the payment using the compute_rate method of the res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            conversion_date = self.env.context.get('l10n_ve_conversion_date') or payment.date or fields.Date.today()
            if (
                payment.currency_id != payment.company_id.currency_id
                and payment.currency_id != payment.company_id.foreign_currency_id
            ):
                rate_values = Rate.compute_rate(
                    payment.currency_id.id, conversion_date
                )
                payment.other_rate = rate_values.get("foreign_rate", 0)
                payment.other_rate_inverse = rate_values.get("foreign_inverse_rate", 0)
            else:
                payment.other_rate = 0
                payment.other_rate_inverse = 0

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.foreign_rate):
                return
            payment.foreign_inverse_rate = Rate.compute_inverse_rate(
                payment.foreign_rate
            )

    @api.onchange("other_rate")
    def _onchange_other_rate(self):
        """
        Onchange the other rate and compute the other inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.other_rate):
                return
            payment.other_rate_inverse = Rate.compute_inverse_rate(payment.other_rate)

    def action_post(self):
        res = super().action_post()
        # Establecer el booleano en todos los pagos en una sola escritura para mayor eficiencia
        self.write({"block_change_partner_after_post": True})
        return res
            

    def action_cancel(self):
        """Cancel payments preserving fiscal traceability.

        Odoo's native behavior physically deletes ('unlink') draft moves
        associated with the payment. This override protects previously
        posted moves (posted_before=True) by cancelling them instead of
        letting them be deleted, while handling the rest of the standard
        flow (posted moves reversal, draft moves cleanup) explicitly.
        """
        for payment in self:
            move = payment.move_id
            if not move:
                continue
            if move.state == 'draft' and not move.posted_before:
                move.unlink()
            elif move.state != 'cancel':
                move.button_cancel()
        self.state = 'canceled'
