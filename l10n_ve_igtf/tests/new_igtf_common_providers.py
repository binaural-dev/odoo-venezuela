# -*- coding: utf-8 -*-
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

        # Configuración de la tasa de cambio
        self.rate = 201.47  # 1 USD = 201.47 VEF
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
            """Busca o crea una cuenta y asegura las propiedades requeridas."""
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

            if not account_record:
                account_record = self.Account.create(values)
            else:
                account_record.write(values)
          
            return account_record
        
        self.get_or_create_account = get_or_create_account 

        # 3. Creación de Cuentas Necesarias (AJUSTADO PARA PROVEEDORES)
        self.acc_receivable = self.get_or_create_account(
            "1101", "asset_receivable", "Cuentas por Cobrar (Clientes)", recon=True
        )
        self.acc_payable = self.get_or_create_account( 
            "2101", "liability_payable", "Cuentas por Pagar (Proveedores)", recon=True
        )
        self.acc_expense = self.get_or_create_account("5001", "asset_current", "Costo de Mercancía/Gasto")
        
        # Cuenta de IGTF (Gasto/Impuesto - Diferente para Proveedores)
        # Usamos una cuenta de IGTF Gasto/Retención para pagos a proveedores
        self.acc_igtf_cli = self.get_or_create_account("523IGTF", "expense", "IGTF Proveedores (Gasto)")
        
        # Cuenta de Banco/Caja que usará el diario
        self.account_bank = self.get_or_create_account("1001", "asset_cash", "Cuenta de Banco USD") 

        self.advance_cust_acc = self.get_or_create_account(
            "21600", "liability_current", "Anticipo Clientes", recon=True
        )
        self.advance_supp_acc = self.get_or_create_account(
            "13600", "asset_current", "Anticipo Proveedores", recon=True
        )

        self.account_bank_bsf = self.get_or_create_account("1001", "asset_cash", "Cuenta de Banco VEF") 


        # 4. Configuración de la Compañía (IGTF y Anticipos)
        self.company.write(
            {
                # Configuración de IGTF (AJUSTADO PARA PROVEEDORES)
                "igtf_percentage": 3.0,
                "supplier_account_igtf_id": self.acc_igtf_cli.id, # Usar la cuenta para proveedores
                
            }
        )
        
        # 5. Métodos de pago
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out") 
        
        # Líneas de método USD (PRIORIZANDO OUTBOUND)
        self.pm_line_in_usd = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound USD",
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

        # Líneas de método VEF (PRIORIZANDO OUTBOUND)
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


        # 6. Configuración de Diarios (AJUSTADO PARA PROVEEDORES)
        self.bank_journal_usd = self.Journal.create(
            {
                "name": "Banco USD IGTF",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
                "is_igtf": True, # IGTF aplica en este diario
                "default_account_id": self.account_bank.id, 
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_usd.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_usd.ids)], # OUTBOUND
            
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
                "default_account_id": self.account_bank_bsf.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_vef.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_vef.ids)], # SOLO OUTBOUND
            }
        )
        self.pm_line_out_vef.journal_id = self.bank_journal_bs.id

        # 7. Partner, Producto y Tax (AJUSTADO PARA PROVEEDOR)
        self.partner = self.env["res.partner"].create(
            {"name": "Proveedor IGTF", 
             "vat": "J123",
             "property_account_receivable_id": self.acc_receivable.id,
             "property_account_payable_id": self.acc_payable.id, # Cuentas por Pagar
             "supplier_rank": 1, # Asegurar que es un proveedor
             "customer_rank": 0,
            }
        )
        
        self.tax_iva_exent = self.env['account.tax'].create({
            'name': 'IVA exento', 'amount': 0, 'amount_type': 'percent', 
            'type_tax_use': 'purchase', # Usar para compra
            'company_id': self.company.id,
        })

        self.product = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "purchase_ok": True, # Asegurar que es para compra
                "property_account_expense_id": self.acc_expense.id, # Usar cuenta de Gasto
                "supplier_taxes_id": [(6, 0, [self.tax_iva_exent.id])],

            }
        )

        # 8. Creación de la Factura de proveedor (Ajuste en la utilidad)
        # self.invoice = self._create_bill_usd(1000.0) # Usaremos _create_bill_rate

  

    def _create_invoice_usd(self, amount):
        line = Command.create(
            {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": amount,
                "tax_ids": [(6, 0, [self.tax_iva_exent.id])],

                "account_id": self.acc_expense.id, 
            }
        )

        purchase_journal = self.Journal.search([("type", "=", "purchase")], limit=1)
        if not purchase_journal:
             purchase_journal = self.Journal.create({
                 'name': 'Diario Compra', 'type': 'purchase', 'code': 'PURC',
                 'company_id': self.company.id, 'currency_id': self.currency_usd.id,
             })

        inv = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "currency_id": self.currency_usd.id,
                "journal_id": purchase_journal.id,
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
        # Ajuste para PAGO SALIENTE (OUTBOUND)
        vals = {
            "payment_type": "outbound", 
            "partner_type": "supplier", # Proveedor
            "partner_id": self.partner.id,
            "amount": amount, 
            "currency_id": (currency or self.currency_usd).id,
            "journal_id": (journal or self.bank_journal_usd).id,
            "payment_method_line_id": (pm_line or self.pm_line_out_usd).id,
            "is_igtf_on_foreign_exchange": is_igtf_on_foreign_exchange,
            "date": fields.Date.today(), 
        }
        
        pay = self.env["account.payment"].create(vals)
        pay.action_post()
        return pay
    
    def _create_invoice_rate(self, amount, date=None): # 💡 ACEPTA FECHA
        purchase_journal = self.Journal.search([("type", "=", "purchase")], limit=1)
        if not purchase_journal:
             purchase_journal = self.Journal.create({
                 'name': 'Diario Compra', 'type': 'purchase', 'code': 'PURC',
                 'company_id': self.company.id, 'currency_id': self.currency_usd.id,
             })

        

       # 1. 📢 PRIMER PASO: CREAR Y GUARDAR ENCABEZADO (Simula guardar el borrador)
        with Form(self.env["account.move"].with_context(default_move_type='in_invoice')) as inv_form:
            #inv_form.move_type = "out_invoice"
            inv_form.correlative = "12345698741256"
            inv_form.partner_id = self.partner
            #inv_form.currency_id = self.currency_usd
            inv_form.journal_id = purchase_journal
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
