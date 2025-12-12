from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    is_igtf = fields.Boolean(string="IGTF", 
                             help="IGTF")
                             
    amount_with_igtf = fields.Float(
        string="Amount with IGTF", 
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
        string="IGTF Amount", 
        help="IGTF Amount"
    )

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        default=False,
        help="IGTF on Foreign Exchange?",
        store=True,
    )

    amount_without_difference = fields.Float(
        string="Amount without Difference",
    )

    payment_difference = fields.Monetary(
        compute='_compute_payment_difference',readonly=False)

    apply_igtf_in_wizard_payment = fields.Boolean(related='company_id.apply_igtf_in_wizard_payment')

    igtf_to_show = fields.Float(string="Amount with IGTF")


    @api.depends('can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', 'payment_date')
    def _compute_amount(self):
        for wizard in self:
            amount = False
            if not wizard.journal_id or not wizard.currency_id or not wizard.payment_date:
                amount = wizard.amount
            elif wizard.source_currency_id and wizard.can_edit_wizard:
                batch_result = wizard._get_batches()[0]
                amount = wizard._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result)[0] 
            else:
                amount = None
            if  wizard.is_igtf and wizard.apply_igtf_in_wizard_payment:
                id=self.env.context.get("active_id",False)
                move_id=self.env['account.move'].browse(id)
                
                igtf = wizard.calculate_igtf_for_payment(move_id,amount,wizard.igtf_percentage)
                sum = amount + igtf
                if move_id.amount_residual < sum:
                    amount += igtf
            wizard.amount = amount


    @api.onchange('payment_difference')
    def _onchange_diference(self):
        for wizard in self:
            if wizard.can_edit_wizard and wizard.payment_date and wizard.is_igtf:
                batch_result = wizard._get_batches()[0]
                
                # 1. Monto residual de la factura (sin IGTF)
                total_residual = wizard\
                    ._get_total_amount_in_wizard_currency_to_full_reconcile(batch_result, early_payment_discount=False)[0]

                # 2. Calcular el MONTO TOTAL ESPERADO (Factura + IGTF, si aplica)
                expected_amount = total_residual
                if wizard.company_id.apply_igtf_in_wizard_payment and wizard.igtf_to_show > 0.00:
                    expected_amount += wizard.igtf_to_show
                    
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

    @api.onchange("igtf_to_show")
    def _compute_amount_without_difference(self):
        for rec in self:
                id=self.env.context.get("active_id",False)
                move_id=self.env['account.move'].browse(id)

                if rec.amount <= move_id.amount_residual + move_id.amount_residual * (rec.igtf_percentage / 100):
                        rec.amount_without_difference = rec.amount - rec.igtf_to_show
                
                elif rec.amount > move_id.amount_residual + move_id.amount_residual * (rec.igtf_percentage / 100) :
                    rec.amount_without_difference = move_id.amount_residual                

    @api.onchange("journal_id","currency_id")
    def _compute_check_igtf(self):
        """ Check if the company is a ordinary contributor"""
        for payment in self:
            payment.is_igtf = False
            if payment.journal_id.is_igtf :

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


    @api.onchange("amount", "igtf_to_show")
    def _compute_amount_with_igtf(self):
        """Compute the amount with igtf of the payment"""
        for payment in self:
            payment.amount_with_igtf = payment.amount + payment.igtf_to_show

    @api.onchange("journal_id", "is_igtf", "is_igtf_on_foreign_exchange", 'amount')
    def _compute_igtf_amount(self):
        for payment in self:
                id=self.env.context.get("active_id",False)
                move_id=self.env['account.move'].browse(id)
                payment.igtf_to_show = payment.calculate_igtf_for_payment(
                        move_id, payment.amount, payment.igtf_percentage
                    )
                payment.igtf_amount = payment.igtf_to_show

    @api.onchange('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id == self.env.ref("base.USD"):
                record.is_igtf_on_foreign_exchange = True
            else:
                record.is_igtf_on_foreign_exchange = False
    
    def calculate_igtf_for_payment(self, invoice, payment_amount, igtf_percentage=False):
       
        currency = self.currency_id 
        
        principal_debt = invoice.amount_residual
        principal_amount = min(payment_amount, principal_debt)
        
        igtf_unrounded = principal_amount * (self.env.company.igtf_percentage / 100)
        
        igtf_top = currency.round(invoice.igtf_top_aply) 
        alter_bi_igtf = currency.round(invoice.alter_bi_igtf)
        igtf= currency.round(igtf_unrounded)
    
        if igtf > 0 and igtf_top == invoice.amount_residual:
            return 0.0
        if igtf > igtf_top and igtf_top >= 0.0:
        
            return 0.0
        
        residual_igtf = (invoice.amount_total * (self.env.company.igtf_percentage / 100)) - alter_bi_igtf
        if igtf > residual_igtf and residual_igtf != 0.0:
            igtf = residual_igtf
            
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

   
    
    
   

