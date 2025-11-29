from odoo import api, fields, models, _
from odoo.tools.sql import column_exists, create_column
from odoo.tools import formatLang
import logging
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round
_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _auto_init(self):
        if not column_exists(self.env.cr, "account_move", "amount_to_pay_igtf"):
            create_column(self.env.cr, "account_move", "amount_to_pay_igtf", "numeric")
            self.env.cr.execute("""
                UPDATE account_move
                SET amount_to_pay_igtf = 0.0
            """)
        if not column_exists(self.env.cr, "account_move", "amount_residual_igtf"):
            create_column(self.env.cr, "account_move", "amount_residual_igtf", "numeric")
            self.env.cr.execute("""
                UPDATE account_move
                SET amount_residual_igtf = 0.0
            """)
        return super()._auto_init()

    bi_igtf = fields.Monetary(string="BI IGTF", help="subtotal with igtf", copy=False, compute='compute_bi_igtf',store=True)
    amount_paid = fields.Monetary(string="Paid", default=0.00, help="Paid", copy=False)

    payment_igtf_id = fields.Many2one(
        "account.payment",
        string="Payment IGTF",
        help="Payment IGTF",
        readonly=True,
        copy=False,
    )

    amount_to_pay_igtf = fields.Monetary(
        string="IGTF Paid",
        default=0.00,
        help="IGTF Paid",
        compute="_compute_amount_to_pay_igtf",
        store=True,
        copy=False,
    )

    amount_residual_igtf = fields.Monetary(
        string="IGTF Residual",
        default=0.00,
        help="IGTF Residual",
        compute="_compute_amount_residual_igtf",
        copy=False,
    )


    #OVERRIDES ODOO COMPUTE METHOD
    @api.depends('move_type', 'line_ids.amount_residual')
    def _compute_payments_widget_reconciled_info(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}

            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move.sudo()._get_all_reconciled_invoice_partials()
                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False

                    #-----------------BINAURAL--------------
                    is_igtf = counterpart_line.payment_id.is_igtf_on_foreign_exchange
                    #-----------------BINAURAL--------------

                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'company_name': counterpart_line.journal_id.company_id.name if counterpart_line.journal_id.company_id != move.company_id else False,
                        #-----------------BINAURAL--------------
                        'amount': reconciled_partial['amount'] + move.amount_to_pay_igtf if is_igtf else reconciled_partial['amount'], 
                        #-----------------BINAURAL--------------
                        'currency_id': move.company_id.currency_id.id if reconciled_partial['is_exchange'] else reconciled_partial['currency'].id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance), currency_obj=counterpart_line.company_id.currency_id),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env, abs(counterpart_line.amount_currency), currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget = payments_widget_vals
            else:
                move.invoice_payments_widget = False


    @api.depends("tax_totals")
    def _compute_amount_to_pay_igtf(self):
        """
        Compute the amount to pay of the IGTF
        """
        for move in self:
            move.amount_to_pay_igtf = 0
            if move.invoice_line_ids and move.is_invoice(include_receipts=True) and move.tax_totals:
                move.amount_to_pay_igtf = move.tax_totals["igtf"]["igtf_amount"] - move.amount_paid

    @api.depends(
        "amount_total", "amount_residual", "amount_residual_igtf", "amount_to_pay_igtf", "bi_igtf"
    )
    def _compute_amount_residual_igtf(self):
        for record in self:
            record.amount_residual_igtf = record.amount_residual + record.amount_to_pay_igtf

            if record.amount_residual and record.amount_to_pay_igtf:
                record.amount_residual_igtf = record.amount_residual + record.amount_to_pay_igtf
            else:
                record.amount_residual_igtf = 0

    @api.depends(
        "bi_igtf",
    )
    def _compute_tax_totals(self):
        return super()._compute_tax_totals()

    @api.depends('amount_residual')
    def compute_bi_igtf(self):
        for rec in self:
            receivable_payable_lines = rec.line_ids.filtered(lambda line: line.account_id.reconcile)

            account = [self.company_id.customer_account_igtf_id.id,self.company_id.supplier_account_igtf_id.id ]
            # Recolectar todos los asientos (move_id) que participaron en la conciliación
            payment_moves = self.env['account.move']
            
            # Mapeo eficiente de todos los partial.reconcile (matched_debit/credit_ids)
            all_partial_reconciles = receivable_payable_lines.matched_debit_ids | receivable_payable_lines.matched_credit_ids
            
            # 3. Recolectar todos los asientos de pago opuestos
            # Usamos el operador '|' para unir los records
            payment_moves |= all_partial_reconciles.mapped('debit_move_id.move_id')
            payment_moves |= all_partial_reconciles.mapped('credit_move_id.move_id')

            final_payment_moves = payment_moves.filtered(lambda m: m.state == 'posted' and m.id != rec.id)
            total_bi_igtf = 0.0
            
            # 4. Procesar y Extraer la Base Imponible por cada Pago
            for payment_move in final_payment_moves:
                
                # Buscar la línea de IGTF y la de Banco/Caja en el asiento de pago actual
                igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_cash','bank'])
                
                # Validar la existencia de ambas líneas
                if igtf_line and bank_line:
                    # Obtenemos el primer elemento de la lista filtrada [0]
                    #monto_igtf = abs(igtf_line[0].balance)
                    base_pago = abs(bank_line[0].balance)
                    # Sumar a los totales y almacenar detalles
                    #total_igtf_monto += monto_igtf
                    total_bi_igtf += base_pago
            
            
            rec.bi_igtf = total_bi_igtf
                    


    def js_remove_outstanding_partial(self, partial_id):
        partial_reconcile = self.env['account.partial.reconcile'].browse(partial_id)
        if not partial_reconcile:
            return super().js_remove_outstanding_partial(partial_id) 
            
        related_moves = partial_reconcile.debit_move_id.move_id | partial_reconcile.credit_move_id.move_id
        
        igtf_account_ids = [
            self.company_id.customer_account_igtf_id.id,
            self.company_id.supplier_account_igtf_id.id
        ]
        
        liquidity_account_types = ['asset_cash', 'bank']
        payment_move = related_moves.filtered(
            lambda move: move.line_ids.filtered(
                lambda line: line.account_id.account_type in liquidity_account_types
            )
        )[:1]

        if not payment_move:
            # Si no es un asiento de pago, solo dejamos que el super elimine la conciliación
            return super().js_remove_outstanding_partial(partial_id) 

        # --- INICIO DEL FLUJO SEGURO ---

        # 2. LLAMAR a super() para Desconciliar (Elimina el partial_reconcile)
        # Esto es crucial para liberar la línea antes de ir a borrador.
        res_super = super().js_remove_outstanding_partial(partial_id)

        # 3. Poner en Borrador (Ahora que la línea está liberada de la conciliación)
        try:
            payment_move.button_draft()
        except Exception:
            # Falla al ir a borrador
            return False
        
        # 4. Buscar líneas clave y aplicar lógica IGTF
        igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in igtf_account_ids)
        receivable_payable_line = payment_move.line_ids.filtered(
            lambda line: line.account_id.id in [payment_move.partner_id.property_account_payable_id.id,payment_move.partner_id.property_account_receivable_id.id ]
        )[:1]
      
        if igtf_line and receivable_payable_line:
        
            currency_rounding = payment_move.currency_id.rounding or 0.01
            igtf_line_balance = float_round(
            igtf_line.balance, 
            precision_rounding=currency_rounding
            )
            
            # 1. Obtenemos el saldo existente en la línea a conciliar (solo un lado debe tener valor)
            current_debit = receivable_payable_line.debit
            current_credit = receivable_payable_line.credit

            # 2. PREPARAR NUEVA LISTA DE LÍNEAS
            new_lines_commands = []
            
            # 3. Iterar sobre las líneas existentes para construir el nuevo listado
            for line in payment_move.line_ids:
                
                # Si la línea es la de IGTF, la omitimos (la eliminamos)
                if line.id == igtf_line.id:
                    new_lines_commands.append((2, line.id, False))
                    
                # Si la línea es la de Cuentas por Cobrar/Pagar, la ajustamos
                elif line.id == receivable_payable_line.id:
                    
                    current_debit = float_round(line.debit, precision_rounding=currency_rounding)
                    current_credit = float_round(line.credit, precision_rounding=currency_rounding)
                    
                    # Determinamos la compensación
                    if igtf_line_balance > 0: # IGTF era DÉBITO
                        new_debit = current_debit + igtf_line_balance
                        new_credit = 0.0
                    else: # IGTF era CRÉDITO
                        new_credit = current_credit + abs(igtf_line_balance)
                        new_debit = 0.0

                    # Creamos el comando de actualización (comando 1: update)
                    line_vals = {
                        'debit': new_debit,
                        'credit': new_credit,
                        # Mantener el resto de campos (cuenta, nombre, etc.)
                        'account_id': line.account_id.id,
                        'name': line.name,
                        # ... (Añadir cualquier otro campo crítico como analytic_tag_ids, etc.)
                    }
                    # Comando (1, ID, VALORES): Actualizar la línea existente
                    new_lines_commands.append((1, line.id, line_vals))
                # Para todas las demás líneas (Caja/Banco, etc.)
                else:
                    # Comando (1, ID, {}): Mantener la línea sin cambios
                    new_lines_commands.append((1, line.id, {}))
            
            # 4. EJECUTAR EL COMANDO DE ESCRITURA GLOBAL
            # Comando (6, 0, [lista de IDs]): Reemplazar TODAS las líneas existentes por las nuevas.
            # En este caso, usamos una lista de comandos (1, ID, vals) para actualizar.
            # Si ejecutamos un simple write, Odoo maneja la eliminación de las líneas no mencionadas.
            #raise UserError('llega aqui')
            payment_move.write({
                'line_ids': new_lines_commands
            })
        # 6. Volver a Publicar
        try:
            payment_move.action_post()
        except Exception:
            # Si falla la publicación, el asiento se queda en borrador.
            return False
            
        return res_super # Devolvemos el resultado del super() para compatibilidad con JS
