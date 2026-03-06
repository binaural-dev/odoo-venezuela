# -*- coding: utf-8 -*-
from odoo.tests import tagged , Form ,TransactionCase


from odoo import fields, Command
import logging

_logger = logging.getLogger(__name__)

class IGTFTestCommon(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Account = self.env["account.account"]
        self.Journal = self.env["account.journal"]
        self.company = self.env.ref("base.main_company")

        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")

        self.currency_vef.rounding = 0.01
        self.currency_usd.rounding = 0.01
        self.currency_usd.decimal_places = 2
        self.currency_vef.decimal_places = 2

        self.rate = 201.47  # 1 USD = 201.47bs
        self.currency_usd.write({
            'rate_ids': [
                Command.create({
                    'company_rate': 1 / self.rate,  
                    'inverse_company_rate': self.rate,
                    'name': fields.Date.today(),
                })
            ],
            'active':True
        })
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "taxpayer_type":'special',
                "country_id": 28,
            }
        )
        
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

        self.acc_receivable = self.get_or_create_account(
            "1101", "asset_receivable", "Cuentas por Cobrar (Clientes)", recon=True
        )
        self.acc_payable = self.get_or_create_account( 
            "2101", "liability_payable", "Cuentas por Pagar (Proveedores)", recon=True
        )
        self.acc_expense = self.get_or_create_account("5001", "asset_current", "Costo de Mercancía/Gasto")
        
        self.acc_igtf_prov = self.get_or_create_account("523IGTF", "expense", "IGTF Proveedores (Gasto)")
        
        self.account_bank = self.get_or_create_account("1001", "asset_cash", "Cuenta de Banco USD") 

        self.acc_igtf_cli = self.get_or_create_account(
            "21600", "liability_current", "Anticipo Clientes", recon=True
        )
        self.advance_supp_acc = self.get_or_create_account(
            "13600", "asset_current", "Anticipo Proveedores", recon=True
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
                "supplier_account_igtf_id": self.acc_igtf_prov.id,
                "advance_customer_account_id": self.acc_igtf_cli.id,
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

        self.pm_line_out_vef = self.env["account.payment.method.line"].create(
            {
                "name": "Manual Outbound VEF",
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank.id, 
            }
        )

        self.bank_journal_usd = self.Journal.create(
            {
                "name": "Banco USD IGTF",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
                "default_account_id": self.account_bank.id, 
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
                "default_account_id": self.account_bank.id,
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_vef.ids)], 
            }
        )
        self.pm_line_out_vef.journal_id = self.bank_journal_bs.id

        self.partner = self.env["res.partner"].create(
            {"name": "Proveedor IGTF", 
             "vat": "J123",
             "property_account_receivable_id": self.acc_receivable.id,
             "property_account_payable_id": self.acc_payable.id, # Cuentas por Pagar
             "supplier_rank": 1, # Asegurar que es un proveedor
             "customer_rank": 0,
             "taxpayer_type":"special",
            }
        )
        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA',
            'country_id': self.company.country_id.id
        })
       
        self.tax_iva_exent = self.env['account.tax'].create({
            'name': 'IVA exento', 'amount': 0, 'amount_type': 'percent', 
            'type_tax_use': 'purchase', # Usar para compra
            'company_id': self.company.id,
            'tax_group_id': self.tax_group.id,  # <--- Esta es la clave
            'country_id': self.company.country_id.id,

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

   
    def _create_invoice_vef(self, amount, date=None): 
        purchase_journal = self.Journal.search([("type", "=", "purchase")], limit=1)
        if not purchase_journal:
             purchase_journal = self.Journal.create({
                 'name': 'Diario Compra', 'type': 'purchase', 'code': 'PURC',
                 'company_id': self.company.id, 'currency_id': self.currency_vef.id,
             })

        with Form(self.env["account.move"].with_context(default_move_type='in_invoice')) as inv_form:
            inv_form.correlative = "12345698741256"
            inv_form.partner_id = self.partner
            inv_form.journal_id = purchase_journal
            inv_form.invoice_date = date or fields.Date.today()
        
        inv = inv_form.save() 

        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        inv = inv_form_edit.save() 


        return inv