from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

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
        alternate_currency = self.env.company.foreign_currency_id.id
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
        compute="_compute_rates",
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
            payment.foreign_rate = rate_values.get("foreign_rate", 0.0)
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

    def _convert_to_wizard_currency(self, installments):
        """Override: convierte cada cuota individualmente.

        El método original agrupa cuotas por moneda y convierte el
        agregado con _convert. Esto introduce error de agregación:

            _convert(Σ amount_i, company_currency)
                ≠ Σ _convert(amount_i, company_currency)

        Nuestro override convierte cada cuota individualmente usando el
        amount_residual (que ya está en moneda compañía y refleja los
        ajustes de porción real), eliminando el error de agregación.

        Esto es especialmente importante para pagos agrupados
        (group_payment=True) donde múltiples facturas se pagan juntas.
        """
        self.ensure_one()
        wizard_curr = self.currency_id
        comp_curr = self.company_currency_id
        total_amount = 0.0
        payment_date = self.payment_date
        for installment in installments:
            line = installment['line']
            curr = line.currency_id
            doc_date = line.date

            if curr == wizard_curr:
                if doc_date == payment_date:
                    total_amount += installment['amount_residual_currency']
                else:
                    total_amount += curr._convert(
                    installment['amount_residual_currency'],
                    wizard_curr,
                    self.company_id,
                    payment_date,
                )


            elif curr != comp_curr and wizard_curr == comp_curr:
                if doc_date == payment_date:
                    total_amount += installment['amount_residual']
                else:
                    total_amount += curr._convert(
                    installment['amount_residual_currency'],
                    wizard_curr,
                    self.company_id,
                    payment_date,
                )


            elif curr == comp_curr and wizard_curr != comp_curr:
                total_amount += comp_curr._convert(
                    installment['amount_residual'],
                    wizard_curr,
                    self.company_id,
                    payment_date,
                )

            else:
                total_amount += curr._convert(
                    installment['amount_residual_currency'],
                    wizard_curr,
                    self.company_id,
                    payment_date,
                )

        return total_amount