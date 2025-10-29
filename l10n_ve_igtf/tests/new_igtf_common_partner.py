from odoo.tests.common import TransactionCase
from odoo.tests.common import Form

from odoo import fields, Command
import logging

_logger = logging.getLogger(__name__)

class IGTFTestCommon(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Account = self.env["account.account"]
        self.Journal = self.env["account.journal"]
        self.company = self.env.ref("base.main_company")

        # 1. Configuración de Monedas
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")

        #self.company.currency_id = self.currency_vef
        self.currency_usd.write({
            
            'active':True
        })
        
        # 💡 Establecer la tasa de cambio USD a VEF (Bolívares) al precio de HOY
        self.rate = 201.47  # 1 USD = 36.50 VEF
        self.currency_vef.write({
            'rate_ids': [
                Command.create({
                    'rate': 1 / self.rate,  # Tasa en Odoo: 1 / VEF por USD
                    'name': fields.Date.today(),
                })
            ],
            'active':True
        })
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
            }
        )
        
        # 2. Funciones Auxiliares (get_or_create_account)
        def get_or_create_account(code, ttype, name, recon=False):
            """Busca o crea una cuenta y asegura las propiedades requeridas. (Lógica corregida)"""
            
            account_record = self.Account.search(
                [("code", "=", code), ("company_id", "=", self.company.id)], limit=1
            )
            
            values = {
                "name": name,
                "code": code,
                "account_type": ttype,
                "reconcile": recon,
                "company_id": self.company.id,
            }

            # 📢 CORRECCIÓN: Si la cuenta existe, la retorna; sino, la crea.
            if not account_record:
                account_record = self.Account.create(values)
            else:
                account_record.write(values) # Asegura que las propiedades sean las correctas
          
            return account_record
        
        # 💡 Hacer la función auxiliar accesible en toda la clase
        self.get_or_create_account = get_or_create_account 

        # 3. Creación de Cuentas Necesarias
        self.acc_receivable = self.get_or_create_account(
            "1101", "asset_receivable", "Cuentas por Cobrar (Clientes)", recon=True
        )
        self.acc_payable = self.get_or_create_account( 
            "2101", "liability_payable", "Cuentas por Pagar (Proveedores)", recon=True
        )
        self.acc_income = self.get_or_create_account("4001", "income", "Ingresos")
        
        # Cuenta de IGTF (Gasto/Impuesto)
        self.acc_igtf_cli = self.get_or_create_account("236IGTF", "expense", "IGTF Clientes")
        
        # Cuenta de Banco/Caja que usará el diario
        # 📢 CORRECCIÓN DE NOMBRE: Usar self.account_bank para consistencia en la clase
        self.account_bank = self.get_or_create_account("1001", "asset_cash", "Cuenta de Banco USD") 

        self.account_bank_bsf = self.get_or_create_account("1001", "asset_cash", "Cuenta de Banco VEF") 


        self.advance_cust_acc = self.get_or_create_account(
            "21600", "liability_current", "Anticipo Clientes", recon=True
        )
        self.advance_supp_acc = self.get_or_create_account(
            "13600", "asset_current", "Anticipo Proveedores", recon=True
        )

        # 4. Configuración de la Compañía (IGTF y Anticipos)
        self.company.write(
            {
                # Configuración de IGTF
                "igtf_percentage": 3.0,
                "customer_account_igtf_id": self.acc_igtf_cli.id,
                
            }
        )
        
        # 6. Método de pago (MOVIDO ARRIBA DE LA SECCIÓN 5)
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out") 
        
        # Creamos las líneas de método de pago. El journal_id es referencial.
        self.pm_line_in_usd = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound USD",
                # 📢 USAR self.account_bank
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank.id, 
            }
        )

        self.pm_line_out_usd = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound USD",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank.id, 
            }
        )


         # 📢 ADICIÓN: Líneas de método VEF
        self.pm_line_in_vef = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound VEF",
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank_bsf.id, 
            }
        )

        self.pm_line_out_vef = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound VEF",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank_bsf.id, 
            }
        )

  

        # 5. Configuración del Diario (IGTF) (AHORA PUEDE REFERENCIAR LAS LÍNEAS)
        self.bank_journal_usd = self.Journal.create(
            {
                "name": "Banco USD IGTF",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
                "is_igtf": True,
                # 📢 USAR self.account_bank
                "default_account_id": self.account_bank.id, 
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_usd.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_usd.ids)],
            
            }
        )
        
        # 📢 AJUSTE NECESARIO: Asignar el journal_id a las líneas de método creadas
        # Esto es necesario para que las líneas de método estén correctamente asociadas.
        self.pm_line_in_usd.journal_id = self.bank_journal_usd.id
        self.pm_line_out_usd.journal_id = self.bank_journal_usd.id

        self.bank_journal_bs = self.Journal.create(
            {
                "name": "Banco VEF (Local)",
                "code": "BVESL",
                "type": "bank",
                "company_id": self.company.id,
                "currency_id": self.currency_vef.id, # Moneda Local VEF
                "is_igtf": False, # Sin IGTF
                "default_account_id": self.account_bank_bsf.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_vef.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_vef.ids)],
            }
        )
        self.pm_line_in_vef.journal_id = self.bank_journal_bs.id

        # 7. Partner, Producto y Tax
        self.partner = self.env["res.partner"].create(
            {"name": "Cliente IGTF", "vat": "J123","property_account_receivable_id": self.acc_receivable.id,
                "property_account_payable_id": self.acc_payable.id,}
        )
        
        self.tax_iva_exent = self.env['account.tax'].create({
            'name': 'IVA exento', 'amount': 0, 'amount_type': 'percent', 
            'type_tax_use': 'sale', 'company_id': self.company.id,
        })

        self.product = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],

            }
        )

        # 8. Creación de la Factura de inicio
        self.invoice = self._create_invoice_usd(1000.0)
        
    # UTILITY: creates a customer invoice in USD
    def _create_invoice_usd(self, amount):
        line = Command.create(
            {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": amount,
                "tax_ids": [(6, 0, [self.tax_iva_exent.id])],
                "account_id": self.acc_income.id, 
            }
        )

        sale_journal = self.Journal.search([("type", "=", "sale")], limit=1)
        if not sale_journal:
             sale_journal = self.Journal.create({
                 'name': 'Diario Venta', 'type': 'sale', 'code': 'SALE',
                 'company_id': self.company.id, 'currency_id': self.currency_usd.id,
             })

        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "currency_id": self.currency_usd.id,
                "journal_id": sale_journal.id,
                "invoice_line_ids": [line],
                "invoice_date": fields.Date.today()

            }
        )
        inv.action_post()
        return inv

    # UTILITY: creates a payment (simplificado para el uso en el test)
    def _create_payment(
        self, amount, *, currency=None, journal=None, is_igtf_on_foreign_exchange=False,
        fx_rate=None, fx_rate_inv=None, pm_line=None, is_advance_payment=False,
    ):
        # Simplificado para fines de la prueba unitaria
        vals = {
            "payment_type": "inbound", 
            "partner_type": "customer", 
            "partner_id": self.partner.id,
            "amount": amount, 
            "currency_id": (currency or self.currency_usd).id,
            "journal_id": (journal or self.bank_journal_usd).id,
            "payment_method_line_id": (pm_line or self.pm_line_in_usd).id,
            "is_igtf_on_foreign_exchange": is_igtf_on_foreign_exchange,
            "date": fields.Date.today(), 
        }
        
        pay = self.env["account.payment"].create(vals)
        pay.action_post()
        return pay
    
    def _create_invoice_rate(self, amount, date=None): # 💡 ACEPTA FECHA
        sale_journal = self.Journal.search([("type", "=", "sale")], limit=1)
        if not sale_journal:
             sale_journal = self.Journal.create({
                 'name': 'Diario Venta', 'type': 'sale', 'code': 'SALE',
                 'company_id': self.company.id, 'currency_id': self.currency_usd.id,
             })

        

      
        # 1. 📢 PRIMER PASO: CREAR Y GUARDAR ENCABEZADO (Simula guardar el borrador)
        with Form(self.env["account.move"].with_context(default_move_type='out_invoice')) as inv_form:
            #inv_form.move_type = "out_invoice"
            inv_form.partner_id = self.partner
            #inv_form.currency_id = self.currency_usd
            inv_form.journal_id = sale_journal
            # Configuramos ambas fechas para asegurar el uso de la tasa correcta
            #inv_form.date = date or fields.Date.today()
            inv_form.invoice_date = date or fields.Date.today()
        
        # Guarda el encabezado (Sale del primer Form context)
        inv = inv_form.save() 
        expected_foreign_rate = self.rate # Tasa directa: 36.50 VEF por 1 USD
        expected_foreign_inverse_rate = 1.0 / self.rate # Tasa inversa: 1 / 36.50

        inv.write({
            'foreign_rate': expected_foreign_rate,
            'foreign_inverse_rate': expected_foreign_inverse_rate,
        })



        # 2. 📢 SEGUNDO PASO: ABRIR LA FACTURA GUARDADA, AGREGAR LÍNEAS Y GUARDAR
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
                #line.tax_ids.add(self.tax_iva_exent)
                # Opcional, forzar la cuenta de ingresos:
                #line.account_id = self.acc_income
        
        # Guarda las líneas
        inv = inv_form_edit.save() 


        return inv


    def get_residual_not_reconcilied(self,move_id):
        """
        Calcula el balance total de todas las líneas de asientos
        (de todos los apuntes) que están completamente reconciliadas.
        """
        # 1. Obtener los IDs de todas las líneas de asientos del conjunto de movimientos.
        all_lines = move_id.line_ids._all_reconciled_lines().filtered(lambda l: l.matched_debit_ids or l.matched_credit_ids)

        total_balance = sum(line.balance for line in all_lines)

        return total_balance
    


    def create_and_post_invoice(self, amount):
        """
        Crea una factura (por defecto de cliente) con IGTF y la registra.
        
        :param float amount: Monto de la factura.
        :param record partner: Partner (si se omite, usa el partner por defecto del test).
        :param str move_type: Tipo de movimiento ('out_invoice' para cliente, 'in_invoice' para proveedor).
        :return: El registro account.move de la factura registrada.
        """
        _logger.info(f"Creating and posting facture for {amount}")
        
        # Asume que _create_invoice_rate es el helper de tu test que incluye el IGTF.
        # Si partner es None, usa el partner predefinido en tu test.
        invoice = self._create_invoice_rate(amount) 
        
        # Registra la factura
        invoice.with_context(move_action_post_alert=True).action_post()
        
        # Verificación básica
        self.assertEqual(invoice.state, 'posted', f"Invoice {invoice.name} must be in posted state.")
        self.assertAlmostEqual(invoice.amount_total, amount,2, f"Invoice total must match {amount}.")
        
        return invoice


    def register_and_verify_overpayment_with_igtf(self, invoice, payment_amount):
        """
        Registra un pago contra una factura, calcula el IGTF, verifica los asientos
        generados y el estado 'paid' de la factura.
        
        :param record invoice: El registro account.move (factura).
        :param float payment_amount: El monto total pagado (incluye el sobrepago).
        :return: (record payment, float cxc_credit_amount, float expected_igtf)
        """
        _logger.info(f"Starting payment registration ({payment_amount}) for invoice {invoice.name}")
        
        # 1. Cálculos esperados
        pct = self.company.igtf_percentage 
        expected_igtf = round(payment_amount * pct / 100, 2)
        # Monto que realmente se aplica a la cuenta por cobrar/pagar
        cxc_credit_amount = payment_amount - expected_igtf 

        # 2. Crear y configurar el wizard de pago
        payment_register_wiz = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids
        ).create({})

        payment_register_wiz.write({
            'amount': payment_amount, 
            'journal_id': self.bank_journal_usd.id, # Asumido en el test original
        })
        
        # 3. Crear el pago y obtener el registro
        action = payment_register_wiz.action_create_payments()
        payment = self.env['account.payment'].browse(action.get('res_id'))
        payment_move = payment.move_id

        # 4. Verificaciones de asientos del pago
        # Adaptar las cuentas según si es cliente o proveedor. Aquí asumimos Cliente (out_invoice)
        expected_lines = [
            {'account': self.account_bank,  'debit': payment_amount, 'credit': 0.0},
            {'account': self.acc_receivable, 'debit': 0.0, 'credit': cxc_credit_amount},
            {'account': self.acc_igtf_cli,  'debit': 0.0, 'credit': expected_igtf},
        ]
        self._assert_move_lines_equal(payment_move, expected_lines)
        
        # 5. Verificación de estado de la factura
        self.assertEqual(invoice.payment_state, 'paid', f"Invoice {invoice.name} must be 'paid'.")
        self.assertAlmostEqual(invoice.amount_residual, 0.0, 2, "Invoice residual must be $0.00.")

        return payment, cxc_credit_amount, expected_igtf


    def find_and_verify_advance_move(self, payment_record, expected_advance_amount):
        """
        Busca el asiento contable de cruce (sobrante) generado por el sobrepago
        y verifica que su monto total coincida con el sobrante esperado.
        
        :param record payment_record: El registro account.payment inicial.
        :param float expected_advance_amount: El monto total esperado del sobrante.
        :return: El registro account.move del sobrante.
        """
        cros_move = self.env['account.move'].search(  
            [('origin_payment_advanced_payment_id', '=', payment_record.id),('is_advance_move','=', True)],
            order='id DESC',  
        
        )[0]
        
        self.assertTrue(cros_move, "Error: Advance/Cros move not found for overpayment.")
        self.assertAlmostEqual(cros_move.amount_total, expected_advance_amount, 2, 
            f"ERROR: Expected advance amount {expected_advance_amount}, but found {cros_move.amount_total}.")
        
        _logger.info(f'Advance Move found: {cros_move.display_name} | Amount: {cros_move.amount_total}')
        return cros_move


    def apply_advance_to_residual(self, advance_move, target_invoice):
        """
        Aplica el crédito pendiente del asiento de avance (sobrante) a una factura.
        
        :param record advance_move: El registro account.move del sobrante.
        :param record target_invoice: La factura a la que se le aplicará el crédito.
        :return: La línea outstanding_line_cros2 (la línea de crédito usada para la conciliación).
        """
        
        # 1. Encontrar la línea contable del sobrante
        # Asume self.advance_cust_acc es la cuenta de anticipos de cliente
        outstanding_line = advance_move.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )  
        self.assertTrue(outstanding_line, "Error: Outstanding credit line not found on advance move.")
        
        # 2. Aplicar el crédito usando el método Odoo (simulando widget)
        target_invoice = self.env['account.move'].search([('id', '=', target_invoice.id)],)

        target_invoice.js_assign_outstanding_line(outstanding_line.id)
        _logger.info(f"Outstanding credit {outstanding_line.id} applied to Invoice {target_invoice.name}.")
        
        # 3. Encontrar el asiento de cruce generado (el que contiene la línea de crédito)
        # Buscamos el último asiento de avance generado para ese pago original
        cros_moves = self.env['account.move'].search(  
            [('origin_payment_advanced_payment_id', '=', advance_move.origin_payment_advanced_payment_id.id),
            ('is_advance_move','=', True)],
            order='id DESC',  
        )
        cros_move_2 = cros_moves[0] if cros_moves else False

        self.assertTrue(cros_move_2, "Error: Second cros move (reconciliation) not found.")

        # 4. Obtener la línea de asiento que se reconcilia contra la factura
        outstanding_line_cros2 = cros_move_2.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.credit > 0
        )
        
        return outstanding_line_cros2
        
    def assert_partial_reconcile_match(self, outstanding_line, invoice_payable_line, expected_amount):
        """
        Verifica que el registro account.partial.reconcile se haya creado.
        
        :param record outstanding_line: Línea de asiento que contiene el crédito (ej: línea de pago).
        :param record invoice_payable_line: Línea CxC/CxP de la factura (el débito que se compensa).
        :param float expected_amount: Monto que se espera haya sido conciliado.
        :return: El registro account.partial.reconcile.
        """
        # La línea de crédito (outstanding_line) usa matched_debit_ids para apuntar a la línea de débito de la factura.
        partial_reconcile = outstanding_line.matched_debit_ids.filtered(
            lambda p: p.debit_move_id == invoice_payable_line
        )
        
        self.assertTrue(partial_reconcile, "Error: Partial reconciliation record not found.")
        self.assertAlmostEqual(partial_reconcile.amount, expected_amount, 2, 
            f"Reconciled amount ({partial_reconcile.amount}) does not match expected amount ({expected_amount}).")
        
        _logger.info(f'Partial reconciliation match successful. Amount: {partial_reconcile.amount}')
        
        return partial_reconcile
    
    def verify_final_advance_residual(self, advance_move, applied_invoice_amount):
        """
        Verifica el sobrante final remanente en la línea de anticipo (advance_move) 
        después de aplicar el crédito a una segunda factura.

        :param record advance_move: El registro account.move del sobrante inicial (cros_move_1).
        :param float applied_invoice_amount: El monto de la factura (invoice_amount_2) que se liquidó con el avance.
        """
        
        # 1. Calcular el IGTF aplicado al monto de la segunda factura
        # El IGTF se calcula sobre el monto de la factura liquidada, que se convierte en gasto al usarse.
        pct = self.company.igtf_percentage
        # La fórmula es idéntica a la que tenías en el test original
        igtf_applied_on_usage = round(applied_invoice_amount * pct / 100, 2)
        
        # 2. Calcular el restante final esperado
        # Sobrante Inicial (amount_total de advance_move) - (Monto Factura Liquidada + IGTF asociado)
        expected_restante_final = advance_move.amount_total - (applied_invoice_amount + igtf_applied_on_usage)
        
        # 3. Verificación
        # Se usa abs() porque get_residual_not_reconcilied puede devolver un valor negativo (crédito pendiente).
        residual_on_move = self.get_residual_not_reconcilied(advance_move)
        
        self.assertAlmostEqual(
            expected_restante_final, 
            abs(residual_on_move), 
            2, 
            f"ERROR: Final advance residual verification failed. Expected: ${expected_restante_final}, "
            f"but advance move residual is ${residual_on_move} (absolute: {abs(residual_on_move)})."
        )
        _logger.info(f"Final advance residual verified. Remaining: ${expected_restante_final}.")

    def unreconcile_last_line_with_invoice(self, target_invoice,move_id_advance ):
        """
        Simula la desconciliación obteniendo el último registro de reconciliación parcial 
        asociado a la factura y llamando al método js_remove_outstanding_partial sobre él.

        Este es el método estándar de Odoo para simular la desconciliación desde la UI (widget).

        :param record target_invoice: La factura a desconciliar.
        :return: True si la desconciliación fue exitosa, False si no se encontró nada.
        """
        target_invoice.ensure_one()
        
        outstanding_line = move_id_advance.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )  
        self.assertTrue(outstanding_line, "Error: No se encontró la línea contable del sobrante para conciliar.")
            
        # 2. Buscar el registro de reconciliación parcial más reciente.
        # Usamos matched_credit_ids porque la línea de la factura es DÉBITO, y fue conciliada con CRÉDITOS.
        

        _logger.info(f"Simulando desconciliación de Factura {target_invoice.name} usando el registro de conciliación parcial ID {outstanding_line.id}.")
        
        # 3. LLAMAR AL MÉTODO DE DESCONCILIACIÓN EN EL REGISTRO (Simulación de UI)
        # Esto es equivalente a pulsar 'Remove' en el widget de conciliaciones.
        target_invoice.js_remove_outstanding_partial(outstanding_line.id)

        #_logger.info(target_invoice.amount_residual)
        #_logger.info(target_invoice.payment_state)
        
        # 4. Invalidar caché para que los siguientes asserts vean los cambios de estado/residuales
        
        _logger.info("Desconciliación simulada exitosamente. Verifique el estado de la factura.")


    
    def get_last_move_reconcilied_with_invoice(self, target_invoice):
        """
        Simula la desconciliación obteniendo el último registro de reconciliación parcial 
        asociado a la factura y llamando al método js_remove_outstanding_partial sobre él.
        
        Retorna el registro account.move (asiento contable) de la línea de crédito que fue desconciliada.

        :param record target_invoice: La factura.
        :return: El registro account.move de la ultima linea reconciliada
        """
        target_invoice = self.env['account.move'].search([('id','=',target_invoice)])

        
        # 1. Encontrar la línea CxC/CxP (débito) de la factura
        invoice_payable_line = target_invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )

        self.assertTrue(invoice_payable_line, "No se encontró línea CxC/CxP para la factura")
       
        # 2. Buscar el registro de reconciliación parcial más reciente.
        # Usamos matched_credit_ids porque la línea de la factura es DÉBITO, y fue conciliada con CRÉDITOS.
        partial_reconcile_records = invoice_payable_line.matched_credit_ids
        
        self.assertTrue(partial_reconcile_records, "No se encontraron registros parcialmente conciliados")
        last_reconcile = partial_reconcile_records.sorted(key='id', reverse=True)[0]
            
        credit_move = last_reconcile.credit_move_id.move_id

        return credit_move
      
