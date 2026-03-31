# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.tests.common import Form

from odoo import fields, Command
import logging

_logger = logging.getLogger(__name__)

class TestCommonSaleInternational(TransactionCase):

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

        self.rate = 201.47 
        self.currency_vef.write({
            'rate_ids': [
                Command.create({
                    'company_rate': self.rate,  
                    'name': fields.Date.today(),
                })
            ],
            'active':True
        })
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
                "country_id": 28,
                "taxpayer_type":'formal',
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
                "default_account_id": self.account_bank.id,
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out_vef.ids)], 
            }
        )
        self.pm_line_out_vef.journal_id = self.bank_journal_bs.id

        self.partner = self.env["res.partner"].create(
            {"name": "Cliente", 
             "vat": "J123",
             "property_account_receivable_id": self.acc_receivable.id,
             "property_account_payable_id": self.acc_payable.id, # Cuentas por Pagar
             "supplier_rank": 0, # Asegurar que es un proveedor
             "customer_rank": 1,
            }
        )
        
        #TAXES GROUPS

        self.tax_group_exempt = self.env['account.tax.group'].create({
            'name': 'IVA EXENTO',
            'company_id': self.company.id
        })

        self.tax_group_zero = self.env['account.tax.group'].create({
            'name': 'IVA CERO INTERNATIONAL',
            'company_id': self.company.id
        })

        self.tax_group_reduced = self.env['account.tax.group'].create({
            'name': 'IVA REDUCIDO',
            'company_id': self.company.id
        })

        self.tax_group_general = self.env['account.tax.group'].create({
            'name': 'IVA GENERAL',
            'company_id': self.company.id
        })

        self.tax_group_extend = self.env['account.tax.group'].create({
            'name': 'IVA EXTENDIDO',
            'company_id': self.company.id
        })

        #INTERNATIONAL TAXES

        self.company.zero_aliquot_sale_international = self.env['account.tax'].create({
            'name': 'IVA cero internacional', 'amount': 0, 'amount_type': 'percent', 
            'type_tax_use': 'sale',
            'company_id': self.company.id,
            'tax_group_id': self.tax_group_zero.id,
        })

        self.company.general_aliquot_sale = self.env['account.tax'].create({
            'name': 'IVA 16%', 'amount': 16, 'amount_type': 'percent', 
            'type_tax_use': 'sale',
            'company_id': self.company.id,
            'tax_group_id': self.tax_group_general.id,
        })

        self.product_zero_aliquot_sale_international = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "sale_ok": True,
                "property_account_expense_id": self.acc_expense.id,
                "taxes_id": [(6, 0, [self.company.general_aliquot_sale.id])],
            }
        )

   
    def _create_invoice_usd(self, amount,product_id, date=None): 

        sequence = self.env["ir.sequence"].sudo().search([("code", "=", "invoice.correlative"), ("company_id", "=", self.env.company.id)])
        sequence.unlink()
        sale_journal = self.Journal.create({
            'name': 'Diario Venta', 'type': 'sale', 'code': 'SAIN',
            'is_debit':True,
            'company_id': self.company.id, 'currency_id': self.currency_usd.id,
            'sequence_number_next':1,
            'refund_sequence_number_next':2,
            'refund_sequence':True,
            'is_sale_international':True,
        })

        sale_journal.sequence_id.use_date_range = False 
        sale_journal.refund_sequence_id.use_date_range = False

        sale_journal.sequence_id.code = "invoice.correlative" 

        with Form(self.env["account.move"].with_context(default_move_type='out_invoice')) as inv_form:
            # inv_form.correlative = "12345698741256"
            inv_form.partner_id = self.partner
            inv_form.journal_id = sale_journal
            inv_form.invoice_date = date or fields.Date.today()
        
        inv = inv_form.save()

        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = product_id if product_id else self.product_zero_aliquot_sale_international
                line.quantity = 1
                line.price_unit = amount
                
        inv = inv_form_edit.save() 

        return inv
    
    def _reverse_invoice_usd(self, move,date=None):

        move_reversal = self.env['account.move.reversal'].with_context(active_model="account.move", active_ids=move.ids).create({
            'date': date or fields.Date.today(),
            'journal_id': move.journal_id.id,
        })

        reversal = move_reversal.reverse_moves()
        reversed_move = self.env['account.move'].browse(reversal['res_id'])
        reversed_move.action_post()
        reversed_move.write({'state': 'posted'})