from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    suggested_custom_amount = fields.Monetary(
        string="Suggested amount",
        currency_field="currency_id",
        compute="_compute_suggested_custom_amount",
        readonly=True,
        store=False,
        help="Suggested amount used when paying invoices involving three distinct currencies. Calculates the equivalent payment amount by converting the open balance from the invoice's original currency, through the company's base currency, to the selected payment currency on the chosen payment date.",
    )

    @api.depends(
        "source_currency_id",
        "currency_id",
        "company_id",
        "company_currency_id",
        "source_amount",
        "source_amount_currency",
        "payment_date",
        "line_ids",
    )
    def _compute_suggested_custom_amount(self):
        """
        Compute the suggested amount when all three conditions are met:
        1. The invoice currency (source_currency_id) differs from the company base currency.
        2. The journal/payment currency (currency_id) differs from the company base currency.
        3. Both currencies are different from each other.

        If the payment date is the same as the invoice date, it calculates the amount
        based on the company currency residual (source_amount) to perfectly match 
        native Odoo rounding.
        If the payment date is different, it calculates based on the original foreign 
        currency residual (source_amount_currency) to accurately reflect exchange rate 
        revaluation over time.
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
                pay_date = record.payment_date or fields.Date.today()
                invoice_date = False

                if record.line_ids:
                    first_line = record.line_ids[0]
                    if hasattr(first_line, 'move_id') and first_line.move_id:
                        invoice_date = first_line.move_id.invoice_date or first_line.date
                    else:
                        invoice_date = getattr(first_line, 'date', False)

                if invoice_date and invoice_date == pay_date:
                    record.suggested_custom_amount = company_currency._convert(
                        record.source_amount,
                        payment_currency,
                        record.company_id,
                        pay_date,
                    )
                else:
                    record.suggested_custom_amount = source_currency._convert(
                        record.source_amount_currency,
                        payment_currency,
                        record.company_id,
                        pay_date,
                    )
            else:
                record.suggested_custom_amount = 0.0
