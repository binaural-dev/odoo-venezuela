from collections import defaultdict
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
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

    indexaxion_payment_mode = fields.Selection(
        related='company_id.indexaxion_payment_mode'
    )

    indexed_default = fields.Boolean(default=lambda self: self.env.company.indexed_default, string="Payment indexed")

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

    def _get_conversion_date(self):
        if not self.indexed_default and self.currency_id != self.company_currency_id:
            invoice_dates = self.line_ids.move_id.filtered(
                lambda m: m.is_invoice(include_receipts=True)
            ).mapped('invoice_date')
            if invoice_dates:
                return min(invoice_dates)
        return self.payment_date

    @api.onchange("indexed_default")
    def _onchange_indexed_default(self):
        if not self.payment_date or not self.currency_id:
            return

        # 1. Guardamos la fecha y la tasa original
        fecha_original = self.payment_date
        wizard_currency = self.currency_id
        company = self.company_id or self.env.company

        # Obtener la tasa de la fecha actual (Odoo busca la más cercana hacia atrás)
        tasa_actual = wizard_currency._get_rates(company, fecha_original).get(wizard_currency.id, 1.0)

        # 2. Buscamos dinámicamente hacia atrás una fecha con tasa distinta
        fecha_con_tasa_diferente = fecha_original
        encontrado = False
        
        # Buscamos hasta 10 días hacia atrás (para cubrir puentes o feriados largos)
        for i in range(1, 10):
            fecha_evaluar = fecha_original - timedelta(days=i)
            tasa_evaluar = wizard_currency._get_rates(company, fecha_evaluar).get(wizard_currency.id, 1.0)
            
            if tasa_evaluar != tasa_actual:
                fecha_con_tasa_diferente = fecha_evaluar
                encontrado = True
                break

        # Si no encontró una tasa diferente (ej. base de datos nueva), restamos 1 día por defecto
        if not encontrado:
            fecha_con_tasa_diferente = fecha_original - timedelta(days=1)

        # 3. Aplicamos el truco del cambio temporal
        self.payment_date = fecha_con_tasa_diferente
        
        # Forzamos a Odoo a ejecutar la lógica de conversión con la tasa vieja
        if hasattr(self, '_compute_amount'):
            self._compute_amount()
            
        # 4. Restauramos la fecha original (Odoo volverá a calcular usando la tasa correcta)
        self.payment_date = fecha_original


    @api.onchange("amount", "payment_date")
    def _onchange_amount(self):
        if self.currency_id == self.company_currency_id and self.indexed_default:
            self.indexed_default = False
        super(AccountPaymentRegister,self)._onchange_amount()


    def _convert_to_wizard_currency(self, installments):
        self.ensure_one()
        conversion_date = self._get_conversion_date()

        total_per_currency = defaultdict(lambda: {
            'amount_residual': 0.0,
            'amount_residual_currency': 0.0,
        })
        for installment in installments:
            line = installment['line']
            total_per_currency[line.currency_id]['amount_residual'] += installment['amount_residual']
            total_per_currency[line.currency_id]['amount_residual_currency'] += installment['amount_residual_currency']

        total_amount = 0.0
        wizard_curr = self.currency_id
        comp_curr = self.company_currency_id
        for currency, amounts in total_per_currency.items():
            amount_residual = amounts['amount_residual']
            amount_residual_currency = amounts['amount_residual_currency']
            if currency == wizard_curr:
                total_amount += amount_residual_currency
            elif currency != comp_curr and wizard_curr == comp_curr:
                total_amount += currency._convert(
                    amount_residual_currency, comp_curr, self.company_id, conversion_date,
                )
            elif currency == comp_curr and wizard_curr != comp_curr:
                total_amount += comp_curr._convert(
                    amount_residual, wizard_curr, self.company_id, conversion_date,
                )
            else:
                total_amount += comp_curr._convert(
                    amount_residual, wizard_curr, self.company_id, conversion_date,
                )
        return total_amount

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