from odoo.exceptions import UserError
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def default_alternate_currency(self):
        """
        This method is used to always return the USD currency as default.

        Returns
        -------
        type = int
            The id of the USD currency
        """
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        return usd_currency.id
    

    def default_alternate_rate(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.foreign_currency_id.id or False

    def default_alternate_rate_display_amount(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        company = self.env.company
        foreign_currency = company.foreign_currency_id

        if not foreign_currency:
            return 0.0

        rate_record = self.env['res.currency.rate'].search([
            ('currency_id', '=', foreign_currency.id),
            ('company_id', '=', company.id),
            ('name', '<=', fields.Date.today())
        ], limit=1, order="name desc")

        if rate_record:
            return rate_record.inverse_company_rate

        return 0.0

    foreign_currency_id = fields.Many2one(
        "res.currency", default=default_alternate_currency
    )

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    foreign_rate = fields.Float(
        help="The rate of the payment",
        digits="Tasa",
        default=default_alternate_rate_display_amount,
        store=True,
    )
    
    foreign_rate_display = fields.Float(
        help="The rate of the payment",
        digits="Tasa",
        compute="_compute_foreign_rate_display",
        string=_("Foreign Rate Display"),
        store=False,
    )
    @api.depends('currency_id', 'payment_date')
    def _compute_foreign_rate_display(self):
        """
        Muestra solo el valor numérico de la tasa de la moneda seleccionada en el campo Importe.
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if payment.currency_id:
                currency_id = payment.currency_id.id
                if currency_id == payment.company_id.currency_id.id:
                    currency_id = payment.company_id.foreign_currency_id.id
                
                rate_values = Rate.compute_rate(
                    currency_id, payment.payment_date
                )
                payment.foreign_rate_display = rate_values.get("foreign_rate", 0.0)
            else:
                payment.foreign_rate_display = 0.0

    foreign_inverse_rate = fields.Float(
        help=(
            "Rate that will be used as factor to multiply of the foreign currency for the payment "
            "and the moves created by the wizard."
        ),
        digits=(16, 15),
        compute="_compute_rates",
        store=True,
    )
    base_currency_is_vef = fields.Boolean(
        default=lambda self: self.env.company.currency_id == self.env.ref("base.VEF")
    )
    
    @api.depends("currency_id")
    def _compute_rates(self):
        """
        Compute the currency and compute the foreign rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.currency_id):
                return
            currency_to_use = payment.currency_id.id if payment.currency_id != payment.company_id.currency_id else payment.company_id.foreign_currency_id.id
            rate_values = Rate.compute_rate(
                currency_to_use, payment.payment_date
            )
            # payment.foreign_rate = rate_values.get("foreign_rate", 0.0)
            payment.foreign_inverse_rate = rate_values.get("foreign_inverse_rate", 0.0)
            

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.foreign_rate):
                return

            batch_results = payment.batches
            payment.foreign_inverse_rate = Rate.compute_inverse_rate(
                payment.foreign_rate
            )

    @api.onchange("payment_date")
    def _onchange_invoice_date(self):
        """
        Onchange the invoice date and compute the foreign rate
        """
        Rate = self.env["res.currency.rate"]
        for payment in self:
            if not bool(payment.payment_date):
                return
            rate_values = Rate.compute_rate(
                payment.foreign_currency_id.id, payment.payment_date
            )
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

    


    def _compute_validation_currency_amount(self):
        """
        Validates that the journal's currency matches the payment amount's currency, unless the journal has no currency.
        If the journal's currency is defined and differs from the payment currency, raises a ValidationError.
        """
        for payment in self:
            journal_currency = payment.journal_id.currency_id
            payment_currency = payment.currency_id
            if not journal_currency:
                continue
            if journal_currency and payment_currency and journal_currency != payment_currency:
                raise UserError(_(
                    "La moneda del diario debe ser igual a la moneda del importe. Diario: %s, Importe: %s"
                ) % (journal_currency.name, payment_currency.name))
            

    def action_create_payments(self):
        """
        Override the action_create_payments method to add the foreign rate and the foreign inverse rate to the payment
        values that are used to create the payment from the wizard.
        """
        self._compute_validation_currency_amount()

        return super().action_create_payments()


    def _compute_validation_currency_amount(self):
        """
        Validates that the journal's currency matches the payment amount's currency, unless the journal has no currency.
        If the journal's currency is defined and differs from the payment currency, raises a ValidationError.
        """
        for payment in self:
            journal_currency = payment.journal_id.currency_id
            payment_currency = payment.currency_id
            if not journal_currency:
                continue
            if journal_currency and payment_currency and journal_currency != payment_currency:
                raise UserError(_(
                    "La moneda del diario debe ser igual a la moneda del importe. Diario: %s, Importe: %s"
                ) % (journal_currency.name, payment_currency.name))
            

    def action_create_payments(self):
        """
        Override the action_create_payments method to add the foreign rate and the foreign inverse rate to the payment
        values that are used to create the payment from the wizard.
        """
        self._compute_validation_currency_amount()

        return super().action_create_payments()
