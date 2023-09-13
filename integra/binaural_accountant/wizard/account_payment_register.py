from odoo import api, fields, models, _


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default value of the foreign currency field

        Returns
        -------
        type = int
            The id of the foreign currency of the company

        """
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    foreign_rate = fields.Float(
        help="The rate of the payment",
        digits="Tasa",
    )
    foreign_inverse_rate = fields.Float(
        help=(
            "Rate that will be used as factor to multiply of the foreign currency for the payment "
            "and the moves created by the wizard."
        ),
        digits=(16, 15),
    )

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.foreign_rate):
                return

            batch_result = payment._get_batches()[0]
            payment.foreign_inverse_rate = Rate.compute_inverse_rate(payment.foreign_rate)
            total_amount_residual_in_wizard_currency = (
                payment._get_total_amount_in_wizard_currency_to_full_reconcile(
                    batch_result, early_payment_discount=False
                )[0]
            )
            payment.amount = total_amount_residual_in_wizard_currency

    @api.onchange("payment_date")
    def _onchange_invoice_date(self):
        """
        Onchange the invoice date and compute the foreign rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.payment_date):
                return
            rate_values = Rate.compute_rate(payment.foreign_currency_id.id, payment.payment_date)
            payment.update(rate_values)

    def _create_payment_vals_from_wizard(self, batch_result):
        """
        This method is used to add the foreign rate and the foreign inverse rate to the payment
        values that are used to create the payment from the wizard.
        """
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals.update(
            {
                "foreign_rate": self.foreign_rate,
                "foreign_inverse_rate": self.foreign_inverse_rate,
            }
        )
        return payment_vals

    @api.depends("can_edit_wizard", "amount", "foreign_inverse_rate")
    def _compute_payment_difference(self):
        for wizard in self:
            if wizard.can_edit_wizard:
                batch_result = wizard._get_batches()[0]
                total_amount_residual_in_wizard_currency = (
                    wizard._get_total_amount_in_wizard_currency_to_full_reconcile(
                        batch_result, early_payment_discount=False
                    )[0]
                )
                wizard.payment_difference = total_amount_residual_in_wizard_currency - wizard.amount
            else:
                wizard.payment_difference = 0.0

    def _get_total_amount_in_wizard_currency_to_full_reconcile(
        self, batch_result, early_payment_discount=True
    ):
        """Compute the total amount needed in the currency of the wizard to fully reconcile the batch of journal
        items passed as parameter.

        :param batch_result:    A batch returned by '_get_batches'.
        :return:                An amount in the currency of the wizard.
        """
        self.ensure_one()
        comp_curr = self.company_id.currency_id
        if self.source_currency_id == self.currency_id:
            # Same currency (manage the early payment discount).
            return self._get_total_amount_using_same_currency(
                batch_result, early_payment_discount=early_payment_discount
            )
        elif self.source_currency_id != comp_curr and self.currency_id == comp_curr:
            # Foreign currency on source line but the company currency one on the opposite line.
            return (
                self.source_currency_id._convert(
                    self.source_amount_currency,
                    comp_curr,
                    self.company_id,
                    self.payment_date,
                ),
                False,
            )
        elif self.source_currency_id == comp_curr and self.currency_id != comp_curr:
            # Company currency on source line but a foreign currency one on the opposite line.
            return (
                abs(
                    sum(
                        comp_curr._convert(
                            aml.amount_residual,
                            self.currency_id,
                            self.company_id,
                            self.payment_date,
                            custom_rate=self.foreign_inverse_rate,
                        )
                        for aml in batch_result["lines"]
                    )
                ),
                False,
            )
        else:
            # Foreign currency on payment different than the one set on the journal entries.
            return (
                comp_curr._convert(
                    self.source_amount,
                    self.currency_id,
                    self.company_id,
                    self.payment_date,
                ),
                False,
            )
