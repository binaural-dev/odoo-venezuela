from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentIgtf(models.Model):
    _inherit = "account.payment"

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        help="IGTF on Foreign Exchange",
        compute="_compute_is_igtf",
        store=True,
    )

    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        compute="_compute_igtf_percentage",
        help="IGTF Percentage",
        store=True,
    )

    igtf_amount = fields.Float(
        string="IGTF Amount",
        compute="_compute_igtf_amount",
        store=True,
        help="IGTF Amount",
    )

    payment_from_wizard = fields.Boolean()
    amount_residual_from_payment = fields.Float()
    
    @api.depends("partner_id")
    def _compute_igtf_percentage(self):
        for payment in self:
            payment.igtf_percentage = payment.env.company.igtf_percentage


    @api.depends("journal_id")
    def _compute_is_igtf(self):
        for payment in self:
            payment.is_igtf_on_foreign_exchange = False
            if payment.journal_id.is_igtf:
                payment.is_igtf_on_foreign_exchange = True

    @api.depends("is_igtf_on_foreign_exchange")
    def _compute_igtf_amount(self):
        for payment in self:
         
            if payment.is_igtf_on_foreign_exchange:
                id=self.env.context.get("active_id",False)
                move_id=self.env['account.move'].browse(id)

                payment.igtf_amount = payment.calculate_igtf_for_payment(move_id,payment.amount,payment.company_id.igtf_percentage)
                   
    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        """Prepare values to create a new account.move.line for a payment.
        this method adds the igtf in the move line values to be created depending on the payment type

        Args:
            write_off_line_vals (dict, optional): Values to create the write-off account.move.line. Defaults to None.

        Returns:
            dict: Values to create the account.move.line.
        """

        vals = super(AccountPaymentIgtf, self)._prepare_move_line_default_vals(
            write_off_line_vals,
            force_balance
        )
        if self.payment_from_wizard:
            if self.igtf_percentage and self.journal_id.is_igtf:
                self._create_igtf_moves_in_payments(vals, write_off_line_vals)

        return vals

    def calculate_igtf_for_payment(self, invoice, payment_amount, igtf_percentage=False):
        """
        Calcula IGTF solo sobre el monto que se aplica a la deuda principal
        """
        currency = self.currency_id 
        
        principal_debt = invoice.amount_residual 
        principal_amount = min(payment_amount, principal_debt)

        result = invoice.amount_residual + (invoice.amount_residual * igtf_percentage / 100)

        if result == invoice.amount_residual :
            
            return 0.0
        
        igtf_unrounded = principal_amount * (self.env.company.igtf_percentage / 100)

        igtf_top = invoice.igtf_top_aply - igtf_unrounded
        if igtf_top != 0 and igtf_unrounded > igtf_top:
            return 0.0
        igtf= currency.round(igtf_unrounded)
        return max(igtf, 0.0)
    
    def _create_igtf_moves_in_payments(self, vals, write_off_line_vals = False):
        """Prepare values to create a new account.move.line for a payment.
        this method adds the igtf in the move line values to be created depending on the payment type

        Args:
            write_off_line_vals (dict, optional): Values to create the write-off account.move.line. Defaults to None.

        Returns:
            dict: Values to create the account.move.line.
        """
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )

        if self._context.get("from_pos", False):
            return

        for payment in self:
            move_id = (
                self.env.context.get("active_id", False)
            )
            move = self.env["account.move"].browse(move_id)
            
            if payment.is_igtf_on_foreign_exchange:
                #aplica solo para igtf
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]

                    if not vals_igtf:
                        payment._prepare_inbound_move_line_igtf_vals(vals, write_off_line_vals)

                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_outbound_move_line_igtf_vals(vals,write_off_line_vals)

    def _create_inbound_move_line_igtf_vals(self, vals):
        """Create the igtf move line values for inbound payments
        this method is called from the _prepare_move_line_default_vals method to add the igtf move line values to the vals list

        Args:
            vals (list): list of move line values

        Returns:
            list: list of move line values with the igtf move line values
        """
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )
        igtf_amount = self.igtf_amount
        account_id = igtf_account if self.igtf_percentage else None
        if igtf_amount > 0.0:
            vals.append(
                {
                    "name": "IGTF",
                    "currency_id": self.currency_id.id,
                    "amount_currency": -igtf_amount,
                    "account_id": account_id,
                    "partner_id": self.partner_id.id,
                }
            )

        return vals

    def _create_outbound_move_line_igtf_vals(self, vals):
        """
        this method is called from the _prepare_move_line_default_vals method to add the igtf move line values to the vals list

        Args:
            vals (list): list of move line values

        Returns:
            list: list of move line values with the igtf move line values

        """
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )
        igtf_amount = self.igtf_amount
        account_id = igtf_account if self.igtf_percentage else None

        if igtf_amount > 0.0:
            vals.append(
                {
                    "name": "IGTF",
                    "currency_id": self.currency_id.id,
                    "amount_currency": igtf_amount,
                    "account_id": account_id,
                    "partner_id": self.partner_id.id,
                }
            )

        return vals

    def _prepare_inbound_move_line_igtf_vals(self, vals, write_off_line_vals = False):
        """
        Prepare the igtf move line values for inbound payments and adjust the principal line
        using Odoo's currency rounding to maintain balance.
        """

        lines = [line for line in vals]
        if self.payment_type == "inbound":
            currency = self.currency_id
            
            
            credit_line_unrounded = lines[1]["amount_currency"] + self.igtf_amount
            #raise UserError(self.igtf_amount)
            # 2. REDONDEAR el monto de la línea de la deuda principal
            credit_line = currency.round(credit_line_unrounded)
            
            # 3. Calcular el monto en la moneda de la compañía (Moneda Base)
            credit_amount = -credit_line # El débito o crédito es el negativo del amount_currency

            # Si la moneda de la compañía es VEF, aplicamos la tasa y redondeamos.
            if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                # Aplicamos la tasa de cambio y redondeamos el monto en moneda base
                credit_amount = currency.round(-credit_line * self.foreign_rate)
            
            # 4. Actualizar la línea de la deuda principal (índice [1])
            if self.igtf_amount > 0:
                vals[1].update({"amount_currency": credit_line, "credit": credit_amount})

            # 5. Llamar al método para AGREGAR la línea de IGTF.
            # Este método auxiliar también debe haber sido actualizado para usar el monto IGTF redondeado.
           
            self._create_inbound_move_line_igtf_vals(vals)
                
    def _prepare_outbound_move_line_igtf_vals(self, vals,write_off_line_vals =False):
        """
        ...
        """
        lines = [line for line in vals]
        if self.payment_type == "outbound":
            currency = self.currency_id
            
            # 1. Calcular el monto en moneda extranjera que va al principal
            # DEBIT_LINE = PAGO ORIGINAL - IGTF
            debit_line_unrounded = lines[1]["amount_currency"] - self.igtf_amount 
            
            # 2. REDONDEAR EL AJUSTE DEL PRINCIPAL USANDO LA DIVISA
            debit_line = currency.round(debit_line_unrounded)
            
            # 3. La línea de IGTF debe ser calculada como el diferencial real
            # Esto corrige cualquier micro-diferencia de redondeo
            igtf_amount_adjusted = currency.round(self.igtf_amount)

            debit_amount = debit_line
            if self.env.company.currency_id.id == self.env.ref("base.VEF").id:
                # Opcional: Asegurar que el monto en VEF también se redondee después de la tasa
                debit_amount = currency.round(debit_line * self.foreign_rate) 
                
            if self.igtf_amount > 0:
                vals[1].update({"amount_currency": debit_line, "debit": debit_amount})

            # Llamamos a la función de creación de IGTF, usando el monto redondeado
            # (Aunque internamente debería usar 'igtf_amount_adjusted', se usa self.igtf_amount 
            # asumiendo que ya fue redondeado en 'calculate_igtf_for_payment').
            self._create_outbound_move_line_igtf_vals(vals)


    @api.depends('journal_id')
    def _compute_is_igtf_journal(self):
        for record in self:
            if record.journal_id.currency_id and record.journal_id.currency_id == self.env.ref("base.USD"):
                record.is_igtf_on_foreign_exchange = True
            else:
                record.is_igtf_on_foreign_exchange = False