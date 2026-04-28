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
        
        
        self.account_bank_vef = self.get_or_create_account("1001", "asset_cash", "Cuenta de Banco VEF") 
        self.account_bank_usd = self.get_or_create_account("1002", "asset_cash", "Cuenta de Banco USd")
        self.account_bank_eur = self.get_or_create_account("1003", "asset_cash", "Cuenta de Banco EUR")

        
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

        "TIPO PERSONA"

        self.pnre = self.env.ref('type_person_l10n_ve_payment_extension')
        self.pndo = self.env.ref('type_person_two_l10n_ve_payment_extension')
        self.pjdo = self.env.ref('type_person_three_l10n_ve_payment_extension')
        self.pjnd = self.env.ref('type_person_four_l10n_ve_payment_extension')
        self.institution = self.env.ref('type_person_five_l10n_ve_payment_extension')
        self.otras = self.env.ref('type_person_six_l10n_ve_payment_extension')
        self.pjrenprice = self.env.ref('type_person_seven_l10n_ve_payment_extension')
        

        "PAYMENT CONCEPT"

        name_concept_1 = 'Honorarios Profesionales Pagados a'
        name_concept_2 = 'Gastos de Transporte (Fletes) Pagados a'
        name_concept_3 = '(Contratista) Ejecución de obras y prestación de servicios en Venezuela pagadas a:'
        name_concept_4 = 'Arrendamiento de bienes muebles pagado a:'
        name_concept_5 = 'Arrendamiento o cesión de uso de bienes inmuebles, pagados al arrendador por personas jurídicas, comunidades o los administradores:'
        name_concept_6 = 'Comisiones pagadas a'

        honorarios = self.env['payment.concept.line'].search([('name','=',name_concept_1)])
        gastos_t = self.env['payment.concept.line'].search([('name','=',name_concept_2)])
        contratista = self.env['payment.concept.line'].search([('name','=',name_concept_3)])
        arrend_bienes_mu = self.env['payment.concept.line'].search([('name','=',name_concept_4)])
        arrend_bienes_inmu = self.env['payment.concept.line'].search([('name','=',name_concept_5)])
        comision = self.env['payment.concept.line'].search([('name','=',name_concept_6)])

        """ PRODUCTS """

        self.product_1 = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "type":'service',
                "payment_concept":honorarios

            }
        )

        self.product_2 = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "type":'service',
                "payment_concept":gastos_t

            }
        )

        self.product_3 = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "type":'service',
                "payment_concept":contratista

            }
        )

        self.product_4 = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "type":'service',
                "payment_concept":arrend_bienes_mu

            }
        )

        self.product_5 = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "type":'service',
                "payment_concept":arrend_bienes_inmu

            }
        )

        self.product_6 = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "type":'service',
                "payment_concept":comision

            }
        )
        

        """ WITHHOLDING """
        self.seventy_percent = self.env.ref('account_withholding_type_75')
        self.undred_percent = self.env.ref('account_withholding_type_100')


        "CONTACTOS"

        self.partner_1 = self.env["res.partner"].create(
            {"name": "Cliente Retencion 100%", 
            "vat": "J123",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id, 
            "taxpayer_type":"formal",
            "withholding_type_id":self.undred_percent,
            "type_person_id":self.pnre
            }
        )

        self.partner_2 = self.env["res.partner"].create(
            {"name": "Cliente Retencion 75%", 
            "vat": "J123",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id, 
            "taxpayer_type":"formal",
            "withholding_type_id":self.seventy_percent,
            "type_person_id":self.pjnd
            }
        )

        """ IMPUESTOS """

        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA',
            'country_id': self.company.country_id.id
        })
        self.tax_iva_exent = self.env['account.tax'].create({
            'name': 'IVA exento', 'amount': 0, 'amount_type': 'percent', 
            'type_tax_use': 'sale', 'company_id': self.company.id,
            'tax_group_id': self.tax_group.id,  
            'country_id': self.company.country_id.id,
        })
        
        """ DIARIOS """
        self.sale_journal_vef = self.Journal.create({
                'name': 'Diario Venta', 'type': 'sale', 'code': 'SALEVEF',
                'company_id': self.company.id, 'currency_id': self.currency_vef.id,
        })

        self.purchase_journal_vef = self.Journal.create({
                'name': 'Diario Compra', 'type': 'purchase', 'code': 'PURVEF',
                'company_id': self.company.id, 'currency_id': self.currency_vef.id,
        })

        self.sale_journal_usd = self.Journal.create({
                'name': 'Diario Venta USD', 'type': 'sale', 'code': 'SALEUSD',
                'company_id': self.company.id, 'currency_id': self.currency_usd.id,
        })

        self.purchase_journal_usd = self.Journal.create({
                'name': 'Diario Compra USD', 'type': 'purchase', 'code': 'PURUSD',
                'company_id': self.company.id, 'currency_id': self.currency_usd.id,
        })

        self.sale_journal_eur = self.Journal.create({
                'name': 'Diario Venta EUR', 'type': 'sale', 'code': 'SALEEUR',
                'company_id': self.company.id, 'currency_id': self.currency_eur.id,
        })

        self.purchase_journal_eur = self.Journal.create({
                'name': 'Diario Compra EUR', 'type': 'purchase', 'code': 'PUREUR',
                'company_id': self.company.id, 'currency_id': self.currency_eur.id,
        })

        """ DIARIOS """


    
    def _create_invoice_vef(self, amount, journal, products, date=None): 
    
        with Form(self.env["account.move"].with_context(default_move_type='out_invoice',default_journal_id=journal)) as inv_form:
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
    
    def _create_invoice_usd(self, amount,journal, date=None): 
      
        with Form(self.env["account.move"].with_context(default_move_type='out_invoice',default_journal_id=journal)) as inv_form:
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
    
    def _create_invoice_eur(self, amount,journal, date=None):

        with Form(self.env["account.move"].with_context(default_move_type='out_invoice',default_journal_id=journal)) as inv_form:
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
        
        inv = inv_form_edit.save() 

        
        return inv
    
    def _create_invoice_provider_vef(self, amount,journal, date=None):
     
        with Form(self.env["account.move"].with_context(default_move_type='in_invoice',default_journal_id=journal)) as inv_form:
            inv_form.correlative = "12345698741256"
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
        
        inv = inv_form_edit.save() 

        
        return inv
    
    def _create_invoice_provider_usd(self, amount,journal, date=None): 
    
        with Form(self.env["account.move"].with_context(default_move_type='in_invoice',default_journal_id=journal)) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.correlative = "12345698741256"
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_usd
            inv_form.save() 
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        
        inv = inv_form_edit.save() 

        
        return inv
    
    def _create_invoice_provider_eur(self, amount,journal, date=None):
    
        with Form(self.env["account.move"].with_context(default_move_type='in_invoice',default_journal_id=journal)) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.correlative = "12345698741256"
            inv_form.invoice_date = date or fields.Date.today()
            inv_form.currency_id = self.currency_eur
            inv_form.save() 
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount        
        inv = inv_form_edit.save() 

        
        return inv