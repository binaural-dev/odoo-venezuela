from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    is_igtf = fields.Boolean(string="IGTF", compute="_compute_check_igtf", help="IGTF", store=True)
    amount_with_igtf = fields.Float(
        string="Amount with IGTF", compute="_compute_amount_with_igtf", store=True
    )

    def _default_igtf_percent_from_company(self):
        return self.env.company.igtf_percentage

    igtf_percentage = fields.Float(
        string="IGTF Percentage Aplicado",
        default=_default_igtf_percent_from_company,
        help="IGTF aplicado, obtenido de la configuración de la compañía en el momento de la creación.",
        store=True,
    )

    igtf_amount = fields.Float(
        string="IGTF Amount", compute="_compute_igtf_amount", store=True, help="IGTF Amount"
    )

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        help="IGTF on Foreign Exchange?",
        compute="_compute_is_igtf_journal",
        store=True,
    )

    amount_without_difference = fields.Float(
        string="Amount without Difference",
        compute="_compute_amount_without_difference",
        store=True,
    )

    amount_with_difference = fields.Float(
        string="Amount with Difference",
        compute="amount_remanent",
        store=True,
    )

    payment_difference = fields.Monetary(
        compute='_compute_payment_difference',readonly=False)

    apply_igtf_in_wizard_payment = fields.Boolean(related='company_id.apply_igtf_in_wizard_payment')


    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date','igtf_amount')
    def _compute_amount(self):
        for wizard in self:
            amount = False
            if not wizard.journal_id or not wizard.currency_id or not wizard.payment_date:
                amount = wizard.amount
            elif wizard.source_currency_id and wizard.can_edit_wizard:
                batch_result = wizard._get_batches()[0]
                amount = wizard._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result)[0] 
            else:
                # The wizard is not editable so no partial payment allowed and then, 'amount' is not used.
                amount = None
            if  wizard.is_igtf and wizard.apply_igtf_in_wizard_payment:
                amount +=  wizard.igtf_amount
            wizard.amount = amount

    @api.onchange('payment_difference')
    def _onchange_diference(self):
        for wizard in self:
            if wizard.can_edit_wizard and wizard.payment_date:
                batch_result = wizard._get_batches()[0]
                
                # 1. Monto residual de la factura (sin IGTF)
                total_residual = wizard\
                    ._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result, early_payment_discount=False)[0]

                # 2. Calcular el MONTO TOTAL ESPERADO (Factura + IGTF, si aplica)
                expected_amount = total_residual
                if wizard.company_id.apply_igtf_in_wizard_payment and wizard.igtf_amount > 0.00:
                    expected_amount += wizard.igtf_amount
                    
                # 3. Calcular la diferencia bruta
                raw_difference = expected_amount - wizard.amount
                
                # 💡 4. Redondear la diferencia a la precisión de la moneda
                # Usamos el redondeo de la moneda del asistente (que es la moneda del pago)
                rounded_difference = float_round(
                    raw_difference, 
                    precision_rounding=wizard.currency_id.rounding
                )
                
                # 5. Forzar el Cero Positivo
                # Si el valor redondeado es -0.00 o 0.00, lo ajustamos a 0.0
                if abs(rounded_difference) < wizard.currency_id.rounding:
                    wizard.payment_difference = 0.0
                else:
                    wizard.payment_difference = rounded_difference
                    
            else:
                wizard.payment_difference = 0.0

    @api.depends("amount","igtf_amount")
    def _compute_amount_without_difference(self):
        for rec in self:
                rec.amount_without_difference = rec.amount - rec.igtf_amount

    @api.depends("amount_without_difference")
    def amount_remanent(self):
        for rec in self:
                rec.amount_with_difference = rec.amount_without_difference + rec.igtf_amount

    @api.depends("journal_id","currency_id")
    def _compute_check_igtf(self):
        """ Check if the company is a ordinary contributor"""
        for payment in self:
            payment.is_igtf = False
            if payment.currency_id.id == self.env.ref("base.USD").id and payment.journal_id.currency_id.id == self.env.ref("base.USD").id:
                for line in payment.line_ids:
                    if (
                        self.env.company.taxpayer_type == "ordinary"
                        and line.move_id.move_type == "out_invoice"
                        
                    ):
                        continue
                    if (
                        self.env.company.taxpayer_type == "ordinary"
                        and line.move_id.partner_id.taxpayer_type == "ordinary"
                        and line.move_id.move_type == "in_invoice"
                    ):
                        continue
                    payment.is_igtf = True


    @api.depends("amount", "is_igtf", "igtf_amount")
    def _compute_amount_with_igtf(self):
        """Compute the amount with igtf of the payment"""
        for payment in self:
            payment.amount_with_igtf = payment.amount + payment.igtf_amount

    @api.depends("amount", "is_igtf", "is_igtf_on_foreign_exchange")
    def _compute_igtf_amount(self):
        """Compute the igtf amount of the payment"""
        for payment in self:
            id=self.env.context.get("active_id",False)
            move_id=self.env['account.move'].browse(id)
            payment.igtf_amount = 0.0
            if (
                payment.journal_id.is_igtf
                and payment.currency_id.id == self.env.ref("base.USD").id
                and payment.is_igtf_on_foreign_exchange
            ):
                payment_amount = payment.amount
                if payment.payment_difference <=0:
                 
                    payment_amount = payment.amount + payment.payment_difference

                payment.igtf_amount = payment.calculate_igtf_for_payment(
                    move_id, payment_amount, payment.igtf_percentage
                ) 

    @api.depends('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id == self.env.ref("base.USD"):
                record.is_igtf_on_foreign_exchange = True
    
              

    def calculate_igtf_for_payment(self, invoice, payment_amount, igtf_percentage):
        """
        Calcula IGTF solo sobre el monto que se aplica a la deuda principal
        """
       
        # 1. Deuda principal pendiente (sin incluir IGTF)
        principal_debt = invoice.amount_total - invoice.bi_igtf 
        principal_amount = min(payment_amount, principal_debt)
        igtf = principal_amount * (igtf_percentage / 100)
        return max(igtf, 0.0)

    def _init_payments(self, to_process, edit_mode=False):
        """Create the payments from the wizard's values.
        IGTF fields are added to the payment values to be created.

        :param to_process: A list of dicts containing the values to create the payments.

        :return: A list of ids of the created payments.
        """
        to_process[0]["create_vals"]["igtf_amount"] = self.igtf_amount
        to_process[0]["create_vals"]["payment_from_wizard"] = True
        to_process[0]["create_vals"]["igtf_percentage"] = self.igtf_percentage
        to_process[0]["create_vals"][
            "is_igtf_on_foreign_exchange"
        ] = self.is_igtf_on_foreign_exchange

        res = super(AccountPaymentRegisterIgtf, self)._init_payments(to_process, edit_mode)
        return res

   
    
    
   

