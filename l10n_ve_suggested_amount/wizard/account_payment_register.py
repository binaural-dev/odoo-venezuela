from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    suggested_custom_amount = fields.Monetary(
        string="Suggested amount",
        currency_field="currency_id",
        compute="_compute_suggested_custom_amount",
        readonly=True,
        store=False,
    )

    @api.depends(
        "source_currency_id",
        "currency_id",
        "company_id",
        "company_currency_id",
        "source_amount",
        "source_amount_currency",
        "payment_date",
    )
    def _compute_suggested_custom_amount(self):
        """
        Compute the suggested amount when all three conditions are met:
        1. The invoice currency (source_currency_id) differs from the company base currency.
        2. The journal/payment currency (currency_id) differs from the company base currency.
        3. Both currencies are different from each other.

        When all three conditions hold, convert source_amount from source_currency_id
        to currency_id using exchange rates effective on payment_date.
        Returns 0.0 otherwise.
        """
        for record in self:
            company_currency = record.company_currency_id
            source_currency = record.source_currency_id
            payment_currency = record.currency_id

            three_currencies_distinct = (
                source_currency
                and payment_currency
                and company_currency
                and source_currency != company_currency
                and payment_currency != company_currency
                and source_currency != payment_currency
            )

            if three_currencies_distinct:
                record.suggested_custom_amount = source_currency._convert(
                    record.source_amount_currency,
                    payment_currency,
                    record.company_id,
                    record.payment_date or fields.Date.today(),
                )
            else:
                record.suggested_custom_amount = 0.0
