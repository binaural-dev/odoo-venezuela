from odoo.tests import tagged , Form ,TransactionCase

from odoo.tools import float_compare
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
        self.currency_vef = self.env.ref("base.VEF") 
        self.currency_usd = self.env.ref("base.USD")
        self.currency_eur = self.env.ref("base.EUR")
        self.currency_vef.rounding = 0.01
        self.currency_usd.rounding = 0.01
        self.currency_eur.rounding = 0.01
        self.currency_usd.decimal_places = 2
        self.currency_vef.decimal_places = 2
        self.currency_eur.decimal_places = 2
        self.currency_vef.write({
            
            'active':True
        })

        self.rate = 390.2944  # 1 USD = 201.47bs
        self.currency_usd.write({
            'rate_ids': [
                Command.create({
                    'company_rate': 1 / self.rate,  
                    'rate': 1 / self.rate,  
                    'inverse_company_rate': self.rate,
                    'name': fields.Date.today(),
                }),
                Command.create({
                    'company_rate': 1 / 380.0000,  
                    'inverse_company_rate': 380.0000,
                    'name': fields.Date.subtract(fields.Date.today(), days=1),
                })
            ],
            'active':True
        })

        self.currency_eur.write({
            'rate_ids': [
                Command.create({
                    'company_rate': 1 / 472.83 ,  
                    'rate': 1 / 472.83 ,  
                    'inverse_company_rate': 472.83 ,
                    'name': fields.Date.today(),
                }),
               
            ],
            'active':True
        })

        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "taxpayer_type":'formal',
                "country_id": 28,
            }
        )
        
        # 2. Funciones Auxiliares (get_or_create_account)
        def get_or_create_account(code, ttype, name, recon=False, is_advance_account=False):
            """Busca o crea una cuenta y asegura las propiedades requeridas. (Lógica corregida)"""
            
            account_record = self.Account.search(
                [("code", "=", code)], limit=1
            )
            
            values = {
                "name": name,
                "code": code,
                "account_type": ttype,
                "reconcile": recon,
                "is_advance_account":is_advance_account
            }

            if not account_record:
                account_record = self.Account.create(values)
            else:
                account_record.write(values) 
          
            return account_record
        
        self.get_or_create_account = get_or_create_account 

        self.acc_receivable = self.get_or_create_account(
            "1101", "asset_receivable", "Cuentas por Cobrar (Clientes)", recon=True,
        )
        self.acc_payable = self.get_or_create_account( 
            "2101", "liability_payable", "Cuentas por Pagar (Proveedores)", recon=True,
        )
        self.acc_income = self.get_or_create_account("4001", "income", "Ingresos")
        self.acc_expense = self.get_or_create_account("5001", "asset_current", "Costo de Mercancía/Gasto")
        
        self.acc_igtf_cli = self.get_or_create_account("236IGTF", "liability_current", "IGTF Clientes")
        self.acc_igtf_prov = self.get_or_create_account("523IGTF", "expense", "IGTF Proveedores (Gasto)")
        
        self.account_bank_vef = self.get_or_create_account("1001", "asset_cash", "Cuenta de Banco VEF") 
        self.account_bank_usd = self.get_or_create_account("1002", "asset_cash", "Cuenta de Banco USd")
        self.account_bank_eur = self.get_or_create_account("1003", "asset_cash", "Cuenta de Banco EUR")

        self.advance_cust_acc = self.get_or_create_account(
            "21600", "liability_current", "Anticipo Clientes", recon=True, is_advance_account=True
        )
        self.advance_supp_acc = self.get_or_create_account(
            "13600", "asset_current", "Anticipo Proveedores", recon=True, is_advance_account = True
        )

        

        self.journal_anticipo = self.Journal.create(
            {
                "name": "Anticipo Clientes IGTF",
                "code": "ANTICIGTF",
                "type": "general",
                "company_id": self.company.id,
               
            }
        )

        self.company.write(
            {
                "igtf_percentage": 3.0,
                "customer_account_igtf_id": self.acc_igtf_cli.id,
                "advance_customer_account_id": self.advance_cust_acc.id,
                "advance_supplier_account_id": self.advance_supp_acc.id,
                "advance_payment_igtf_journal_id": self.journal_anticipo.id,
            }
        )
        
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out") 
        
        self.pm_line_in_usd = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound USD",
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank_usd.id, 
            }
        )

        self.pm_line_out_usd = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound USD",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank_usd.id, 
            }
        )


        self.pm_line_in_vef = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound VEF",
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank_vef.id, 
            }
        )

        self.pm_line_out_vef = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound VEF",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank_vef.id, 
            }
        )

        self.pm_line_in_eur = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound EUR",
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank_eur.id, 
            }
        )

        self.pm_line_out_eur = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound EUR",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank_eur.id, 
            }
        )

        self.bank_journal_usd = self.Journal.create(
            {
                "name": "Banco USD IGTF",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
                "is_igtf": True,
                "default_account_id": self.account_bank_usd.id, 
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_usd.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_usd.ids)],
            
            }
        )

        
        
        self.pm_line_in_usd.journal_id = self.bank_journal_usd.id
        self.pm_line_out_usd.journal_id = self.bank_journal_usd.id

        self.bank_journal_bs = self.Journal.create(
            {
                "name": "Banco VEF (Local)",
                "code": "BVESL",
                "type": "bank",
                "company_id": self.company.id,
                "currency_id": self.currency_vef.id,
                "is_igtf": False, 
                "default_account_id": self.account_bank_vef.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_vef.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_vef.ids)],
            }
        )

        self.pm_line_in_vef.journal_id = self.bank_journal_bs.id
        self.pm_line_out_vef.journal_id = self.bank_journal_bs.id

        self.bank_journal_eur = self.Journal.create(
            {
                "name": "Banco EUR (Local)",
                "code": "EURSL",
                "type": "bank",
                "company_id": self.company.id,
                "currency_id": self.currency_eur.id,
                "is_igtf": True, 
                "default_account_id": self.account_bank_eur.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_eur.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_eur.ids)],
            }
        )

        self.pm_line_in_eur.journal_id = self.bank_journal_eur.id
        self.pm_line_out_eur.journal_id = self.bank_journal_eur.id

        

        self.partner = self.env["res.partner"].create(
            {"name": "Cliente IGTF", 
            "vat": "J123",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id, 
            "taxpayer_type":"formal",
            "default_advance_customer_account_id":self.advance_cust_acc.id,
            "default_advance_supplier_account_id":self.advance_supp_acc.id
            }
        )
        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA',
            'country_id': self.company.country_id.id
        })
        self.tax_iva_exent = self.env['account.tax'].create({
            'name': 'IVA exento', 'amount': 0, 'amount_type': 'percent', 
            'type_tax_use': 'sale', 'company_id': self.company.id,
            'tax_group_id': self.tax_group.id,  # <--- Esta es la clave
            'country_id': self.company.country_id.id,
        })

        self.product = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],

            }
        )



    def _create_invoice_vef(self, amount, date=None): # 💡 ACEPTA FECHA
        sale_journal = self.Journal.search([("type", "=", "sale")], limit=1)
        if not sale_journal:
             sale_journal = self.Journal.create({
                 'name': 'Diario Venta', 'type': 'sale', 'code': 'SALE',
                 'company_id': self.company.id, 'currency_id': self.currency_vef.id,
             })

      
        with Form(self.env["account.move"].with_context(default_move_type='out_invoice',default_journal_id=sale_journal)) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_vef
            inv_form.save() 
            
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        
        # Guarda las líneas
        inv = inv_form_edit.save() 

        
        return inv
    

    def assert_invoice_values(self, invoice, expected_bi_igtf, expected_residual, expected_state):
        """
        Método de ayuda para verificar los valores. 
        Lanza AssertionError si los valores no coinciden, lo cual falla el test.
        """
        

        # Comparación de importes usando float_compare (Precisión contable)
        # Retorna 0 si son iguales según la precisión de la moneda
        prec = invoice.company_currency_id.decimal_places

        if expected_residual >= 0.0:

            self.assertAlmostEqual(expected_residual, invoice.amount_residual, 2,  f"Importe residual incorrecto. Esperado: {expected_residual}, Encontrado: {invoice.amount_residual}")
            

        if float_compare(invoice.bi_igtf, expected_bi_igtf, precision_digits=prec) != 0:
            raise AssertionError(
                f"Base IGTF incorrecta. Esperada: {expected_bi_igtf}, Encontrada: {invoice.bi_igtf}"
            )
        
        # Comparación de Estado
        self.assertEqual(
            invoice.payment_state, expected_state, 
            f"El estado debería ser {expected_state} pero es {invoice.payment_state}"
        )


    def assert_payment_values(self, payment, price, igtf_amount, expected_state, acc_igtf):
        """
        Valida el pago, que el asiento tenga 3 líneas y que la línea de IGTF 
        tenga el monto correcto en la cuenta indicada.
        """
        # 1. Validación de estado y monto base del pago
        if expected_state:
            self.assertEqual(payment.state, expected_state, f"Estado esperado {expected_state}, encontrado {payment.state}")
        
        prec = payment.currency_id.decimal_places
        if price:
            if float_compare(payment.amount, price, precision_digits=prec) != 0:
                raise AssertionError(f"Monto del pago incorrecto: {payment.amount} vs {price}")

        # 2. Validar que el pago esté publicado para que tenga asiento contable
        move = payment.move_id
        if not move:
            raise AssertionError("El pago no tiene un asiento contable (move_id) asociado.")
        
        if igtf_amount and acc_igtf:
            # 3. Verificar que el asiento tenga exactamente 3 líneas (Banco, Cliente, IGTF)
            lineas = move.line_ids
            self.assertEqual(len(lineas), 3, f"El asiento debería tener 3 líneas, pero tiene {len(lineas)}")

            # 4. Buscar la línea de IGTF por la cuenta contable
            # Filtramos las líneas que tengan la cuenta especificada (acc_igtf_cli es un objeto de account.account)
            linea_igtf = lineas.filtered(lambda l: l.account_id.id == acc_igtf.id)

            if not linea_igtf:
                raise AssertionError(f"No se encontró ninguna línea contable con la cuenta {acc_igtf.display_name}")
        
            if len(linea_igtf) > 1:
                raise AssertionError("Se encontró más de una línea con la cuenta de IGTF.")

            # 5. Verificar el monto de la línea de IGTF
            # En un pago (recibo), el IGTF suele ser un débito (aumento de gasto/impuesto)
            # Usamos balance o debit/credit según la lógica de tu localización
            find_amount = abs(linea_igtf.amount_currency)
            
            if float_compare(find_amount, igtf_amount, precision_digits=prec) != 0:
                raise AssertionError(
                    f"Monto IGTF en asiento incorrecto. Esperado: {igtf_amount}, Encontrado: {find_amount} "
                    f"en la cuenta {acc_igtf.code}")

       
   
    def _create_invoice_usd(self, amount, date=None): # 💡 ACEPTA FECHA
        sale_journal = self.Journal.search([("type", "=", "sale")], limit=1)
        if not sale_journal:
             sale_journal = self.Journal.create({
                 'name': 'Diario Venta', 'type': 'sale', 'code': 'SALE',
                 'company_id': self.company.id, 'currency_id': self.currency_vef.id,
             })

      
        with Form(self.env["account.move"].with_context(default_move_type='out_invoice',default_journal_id=sale_journal)) as inv_form:
            inv_form.partner_id = self.partner
            
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_usd
            inv_form.save() 
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        
        # Guarda las líneas
        inv = inv_form_edit.save() 

        
        return inv
    
    def _create_invoice_eur(self, amount, date=None): # 💡 ACEPTA FECHA
        sale_journal = self.Journal.search([("type", "=", "sale")], limit=1)
        if not sale_journal:
             sale_journal = self.Journal.create({
                 'name': 'Diario Venta', 'type': 'sale', 'code': 'SALE',
                 'company_id': self.company.id, 'currency_id': self.currency_vef.id,
             })

      
        with Form(self.env["account.move"].with_context(default_move_type='out_invoice',default_journal_id=sale_journal)) as inv_form:
            inv_form.partner_id = self.partner
            
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_eur
            inv_form.save() 
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        
        # Guarda las líneas
        inv = inv_form_edit.save() 

        
        return inv