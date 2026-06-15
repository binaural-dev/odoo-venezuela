from odoo.tests import  Form ,TransactionCase
import random
from odoo import fields, Command
import logging
_logger = logging.getLogger(__name__)

class RetentionTestCommon(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Account = self.env["account.account"]
        self.Journal = self.env["account.journal"]
        self.company = self.env.ref("base.main_company")
        

        # 1. Configuración de Monedas
        self.currency_vef = self.env.ref("base.VEF") 
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef.rounding = 0.01
        self.currency_usd.rounding = 0.01
        self.currency_usd.decimal_places = 2
        self.currency_vef.decimal_places = 2
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


        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "taxpayer_type":'formal',
                "country_id": 28,
            }
        )

        # Concepto 1: Honorarios Profesionales Pagados a
        self.concept_one = self.env.ref('l10n_ve_payment_extension.payment_concept_one_l10n_ve_payment_extension', raise_if_not_found=False)
        if not self.concept_one:
            self.concept_one = self.env['payment.concept'].search([('name', 'ilike', 'Honorarios Profesionales')], limit=1)

        # Concepto 2
        self.concept_two = self.env.ref('l10n_ve_payment_extension.payment_concept_two_l10n_ve_payment_extension', raise_if_not_found=False)
        if not self.concept_two:
            self.concept_two = self.env['payment.concept'].search([('name', 'ilike', 'Comisiones')], limit=1)

        # Concepto 3
        self.concept_three = self.env.ref('l10n_ve_payment_extension.payment_concept_three_l10n_ve_payment_extension', raise_if_not_found=False)
        if not self.concept_three:
            self.concept_three = self.env['payment.concept'].search([('name', 'ilike', 'Intereses')], limit=1)

        # Concepto 4
        self.concept_four = self.env.ref('l10n_ve_payment_extension.payment_concept_four_l10n_ve_payment_extension', raise_if_not_found=False)
        if not self.concept_four:
            self.concept_four = self.env['payment.concept'].search([('name', 'ilike', 'Arrendamientos')], limit=1)

        # Concepto 5
        self.concept_five = self.env.ref('l10n_ve_payment_extension.payment_concept_five_l10n_ve_payment_extension', raise_if_not_found=False)
        if not self.concept_five:
            self.concept_five = self.env['payment.concept'].search([('name', 'ilike', 'Fletes')], limit=1)

        # Concepto 6
        self.concept_six = self.env.ref('l10n_ve_payment_extension.payment_concept_six_l10n_ve_payment_extension', raise_if_not_found=False)
        if not self.concept_six:
            self.concept_six = self.env['payment.concept'].search([('name', 'ilike', 'Publicidad')], limit=1)

        # Concepto 7
        self.concept_seven = self.env.ref('l10n_ve_payment_extension.payment_concept_seven_l10n_ve_payment_extension', raise_if_not_found=False)
        if not self.concept_seven:
            self.concept_seven = self.env['payment.concept'].search([('name', 'ilike', 'Ganancias')], limit=1)
        
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
                #"is_advance_account":is_advance_account
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

        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out") 
        
        self.pm_line_in_sup_ret = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound supplier retention",
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank_vef.id, 
            }
        )

        self.pm_line_out_sup_ret = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound supplier retention",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank_vef.id, 
            }
        )


        self.pm_line_in_sup = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound VEF",
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank_vef.id, 
            }
        )

        self.pm_line_out_sup = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound VEF",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank_vef.id, 
            }
        )

       

        self.bank_journal_sup_ret = self.Journal.create(
            {
                "name": "Banco Retention Supplyer",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_vef.id,
                "company_id": self.company.id,
                "default_account_id": self.account_bank_vef.id, 
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_sup_ret.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_sup_ret.ids)],
            
            }
        )

        
        
        self.pm_line_in_sup_ret.journal_id = self.bank_journal_sup_ret.id
        self.pm_line_out_sup_ret.journal_id = self.bank_journal_sup_ret.id

        self.bank_journal_sub = self.Journal.create(
            {
                "name": "Banco Retention Cliente",
                "code": "BVESL",
                "type": "bank",
                "company_id": self.company.id,
                "currency_id": self.currency_vef.id,
                "default_account_id": self.account_bank_vef.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in_sup.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_sup.ids)],
            }
        )

        self.pm_line_in_sup.journal_id = self.bank_journal_sub.id
        self.pm_line_out_sup.journal_id = self.bank_journal_sub.id

        self.tax_unit = self.env["tax.unit"].create({
            "name": "UT ISLR Test",
            "value": 100.0,
            "available_date": fields.Date.today(),
            "status": True,
        })
        self.islr_tariff = self.env["fees.retention"].create({
            "name": "ISLR 3% Test",
            "percentage": 3.0,
            "accumulated_rate": False,
            "tax_unit_ids": self.tax_unit.id,
            "status": True,
        })
        self.islr_concept_line = self.env["payment.concept.line"].create({
            "pay_from": 0.0,
            "type_person_id": self.env.ref(
                "l10n_ve_payment_extension.type_person_l10n_ve_payment_extension"
            ).id,
            "payment_concept_id": self.concept_one.id,
            "percentage_tax_base": 90.0,
            "tariff_id": self.islr_tariff.id,
            "code": "ISLR-TEST-90-3",
             }
        )

        self.partner_pnr_75 = self.env["res.partner"].create(
            {"name": "Cliente", 
            "vat": "J123",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id, 
            "taxpayer_type":"formal",
            "type_person_id": self.env.ref("l10n_ve_payment_extension.type_person_l10n_ve_payment_extension").id,
            "withholding_type_id": self.env.ref("l10n_ve_payment_extension.account_withholding_type_75").id,
            }
        )

        self.partner_pnr_100 = self.env["res.partner"].create(
            {"name": "Cliente", 
            "vat": "J123",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id, 
            "taxpayer_type":"formal",
            "type_person_id": self.env.ref("l10n_ve_payment_extension.type_person_l10n_ve_payment_extension").id,
            "withholding_type_id": self.env.ref("l10n_ve_payment_extension.account_withholding_type_100").id,
            }
        )

        self.partner_pnnr_100 = self.env["res.partner"].create(
            {"name": "Cliente", 
            "vat": "J123",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id, 
            "taxpayer_type":"formal",
            "type_person_id": self.env.ref("l10n_ve_payment_extension.type_person_two_l10n_ve_payment_extension").id,
            "withholding_type_id": self.env.ref("l10n_ve_payment_extension.account_withholding_type_100").id,
            }
        )

        self.partner_ordinary = self.env["res.partner"].create(
            {"name": "Cliente", 
            "vat": "J123",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id, 
            "taxpayer_type":"ordinary",
            }
        )


        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA Exent',
            'company_id': self.company.id,
            'country_id': self.company.country_id.id
        })

        self.tax_group_iva = self.env['account.tax.group'].create({
            'name': 'IVA l10n_ve',
            'company_id': self.company.id,
            'country_id': self.company.country_id.id
        })

        self.tax_iva_16 = self.env['account.tax'].create({
            'name': 'IVA 16% Ventas', 
            'amount_type': 'percent', 
            'amount': 16.0,
            'type_tax_use': 'sale', 
            'company_id': self.company.id,
            'tax_group_id': self.tax_group_iva.id,
            'country_id': self.company.country_id.id,
        })

        self.tax_iva_exent = self.env['account.tax'].create({
            'name': 'IVA exento', 'amount': 0, 'amount_type': 'percent', 
            'type_tax_use': 'sale', 'company_id': self.company.id,
            'tax_group_id': self.tax_group.id,  
            'country_id': self.company.country_id.id,
        })

        self.tax_iva_16_purchase = self.env['account.tax'].create({
            'name': 'IVA 16% Compras', 
            'amount_type': 'percent', 
            'amount': 16.0,
            'type_tax_use': 'purchase', 
            'company_id': self.company.id,
            'tax_group_id': self.tax_group_iva.id,
            'country_id': self.company.country_id.id,
        })

        self.tax_iva_exent_purchase = self.env['account.tax'].create({
            'name': 'IVA exento Compras', 
            'amount_type': 'percent', 
            'amount': 0.0, 
            'type_tax_use': 'purchase', 
            'company_id': self.company.id,
            'tax_group_id': self.tax_group.id,  
            'country_id': self.company.country_id.id,
        })

        self.product = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_iva_exent_purchase.id])],
            }
        )

        self.product_iva = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_16.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_iva_16_purchase.id])],

            }
        )

        self.product_islr_one = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_iva_exent_purchase.id])],
                "type": "service",
                "payment_concept": self.concept_one.id


            }
        )

        self.product_islr_three = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_iva_exent_purchase.id])],
                "type": "service",
                "payment_concept": self.concept_three.id


            }
        )

        self.product_islr_iva_three = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_16.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_iva_16_purchase.id])],
                "type": "service",
                "payment_concept": self.concept_three.id
            }
        )

        self.product_islr_iva_one = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
                "taxes_id": [(6, 0, [self.tax_iva_16.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_iva_16_purchase.id])],
                "type": "service",
                "payment_concept": self.concept_one.id
            }
        )

        sequence_sale = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        sequence_purchase = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "PUR/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        self.sale_journal = self.Journal.create({
                 'name': 'Diario Venta', 'type': 'sale', 'code': 'SALE',
                 'company_id': self.company.id, 'currency_id': self.currency_vef.id,
                 'sequence_id': sequence_sale.id,
             })
        
        self.purchase_journal = self.Journal.create({
                'name': 'Diario Compra', 'type': 'purchase', 'code': 'PURC',
                'company_id': self.company.id, 'currency_id': self.currency_vef.id,
                'sequence_id': sequence_purchase.id,
            })

        self.company.write(
            {
                "iva_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
                "iva_customer_retention_journal_id": self.bank_journal_sub.id,
                "islr_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
                "islr_customer_retention_journal_id": self.bank_journal_sub.id,
                "condition_withholding_id": self.env.ref("l10n_ve_payment_extension.account_withholding_type_75"),
            }
        )


    def _create_invoice_reten_iva(self, amount,partner ,out_invoice=None,journal=None): 
        
        with Form(self.env["account.move"].with_context(default_move_type=out_invoice,default_journal_id=journal)) as inv_form:
            inv_form.partner_id = partner
            inv_form.invoice_date = fields.Date.today()
            inv_form.currency_id = self.currency_vef
            if out_invoice == "in_invoice":
                # Genera un número entero aleatorio de 14 dígitos y lo convierte a string
                inv_form.correlative = str(random.randint(10000000000000, 99999999999999))
            
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = amount
        
        inv = inv_form_edit.save() 

        
        return inv


    def _create_invoice_islr(self, amount,partner ,out_invoice=None,journal=None): 
        
        with Form(self.env["account.move"].with_context(default_move_type=out_invoice,default_journal_id=journal)) as inv_form:
            inv_form.partner_id = partner
            inv_form.invoice_date = fields.Date.today()
            inv_form.currency_id = self.currency_vef
            if out_invoice == "in_invoice":
                # Genera un número entero aleatorio de 14 dígitos y lo convierte a string
                inv_form.correlative = str(random.randint(10000000000000, 99999999999999))
            
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_islr_one
                line.quantity = 1
                line.price_unit = amount
        
        inv = inv_form_edit.save() 

        
        return inv
    

    def _create_invoice_islr_iva(self, amount,partner ,out_invoice=None,journal=None): 
        
        with Form(self.env["account.move"].with_context(default_move_type=out_invoice,default_journal_id=journal)) as inv_form:
            inv_form.partner_id = partner
            inv_form.invoice_date = fields.Date.today()
            inv_form.currency_id = self.currency_vef
            if out_invoice == "in_invoice":
                # Genera un número entero aleatorio de 14 dígitos y lo convierte a string
                inv_form.correlative = str(random.randint(10000000000000, 99999999999999))
                
        
        inv = inv_form.save() 
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_islr_iva_one
                line.quantity = 1
                line.price_unit = amount
        
        inv = inv_form_edit.save() 

        
        return inv
    
