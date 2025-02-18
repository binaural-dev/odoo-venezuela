from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.currency_foreign_id.id or False

    foreign_currency_id = fields.Many2one(
        "res.currency", default=default_alternate_currency
    )

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    concept = fields.Char()

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

    @api.depends("date")
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

    # @api.model
    # def _get_trigger_fields_to_synchronize(self):
    #     original_fields = super()._get_trigger_fields_to_synchronize()
    #     additional_fields = ("foreign_rate", "foreign_inverse_rate")
    #     return original_fields + additional_fields
