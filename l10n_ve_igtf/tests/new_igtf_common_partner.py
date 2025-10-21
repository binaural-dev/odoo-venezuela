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
