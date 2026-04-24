from odoo import api, fields, models, _

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

    def default_rate(self):
        """
        This method is used to get the rate of the payment.

        Returns
        -------
        type = float
            The rate of the payment
        """
        rate_values = self.env["res.currency.rate"].compute_rate(
            self.foreign_currency_id.id or self.company_id.currency_id,
            self.date or fields.Date.today(),
        )
        rate = rate_values.get("foreign_rate", 0)
        return rate

    def default_inverse_rate(self):
        """
        This method is used to get the inverse rate of the payment.

        Returns
        -------
        type = float
            The inverse rate of the payment
        """
        rate_values = self.env["res.currency.rate"].compute_rate(
            self.foreign_currency_id.id or self.company_id.currency_id,
            self.date or fields.Date.today(),
        )
        rate = rate_values.get("foreign_inverse_rate", 0)
        return rate


    foreign_rate = fields.Float(
        compute="_compute_rate",
        default=default_rate,
        digits="Tasa",
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        default=default_inverse_rate,
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

    @api.depends("amount", "currency_id")
    def _compute_foreign_amount(self):
        for payment in self:
            if payment.currency_id != payment.foreign_currency_id:
                payment.foreign_amount = payment.currency_id._convert(
                    payment.amount,
                    payment.foreign_currency_id,
                    payment.company_id,
                    payment.date or fields.Date.today(),
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
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            rate_values = Rate.compute_rate(
                payment.foreign_currency_id.id, payment.date or fields.Date.today()
            )
            payment.update(rate_values)

    @api.depends("date", "currency_id")
    def _compute_other_rate(self):
        """
        Compute the visual rate of the payment using the compute_rate method of the res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if (
                payment.currency_id != payment.company_id.currency_id
                and payment.currency_id != payment.company_id.foreign_currency_id
            ):
                rate_values = Rate.compute_rate(
                    payment.currency_id.id, payment.date or fields.Date.today()
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
            

    # @api.model
    # def _get_trigger_fields_to_synchronize(self):
    #     original_fields = super()._get_trigger_fields_to_synchronize()
    #     additional_fields = ("foreign_rate", "foreign_inverse_rate")
    #     return original_fields + additional_fields
