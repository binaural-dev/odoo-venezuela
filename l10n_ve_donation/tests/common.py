from odoo import fields, Command
from odoo.tests import TransactionCase


class TestDonationCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.partner_id.write({
            "customer_rank": 1,
            "supplier_rank": 1,
        })
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_vef = cls.env.ref("base.VEF")

        # Partner
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
            "customer_rank": 1,
            "supplier_rank": 1,
            "country_id": cls.env.ref("base.ve").id,
            "email": "test@example.com",
        })

        # Accounts
        cls.account_income = cls.env["account.account"].create({
            "name": "Income Test",
            "code": "410001",
            "account_type": "income",
            "company_id": cls.company.id,
        })
        cls.account_expense = cls.env["account.account"].create({
            "name": "Expense Test",
            "code": "610001",
            "account_type": "expense",
            "company_id": cls.company.id,
        })
        cls.account_receivable = cls.env["account.account"].create({
            "name": "Receivable Test",
            "code": "110001",
            "account_type": "asset_receivable",
            "company_id": cls.company.id,
        })
        cls.account_payable = cls.env["account.account"].create({
            "name": "Payable Test",
            "code": "210001",
            "account_type": "liability_payable",
            "company_id": cls.company.id,
        })

        # Assign to partner
        cls.partner.write({
            "property_account_receivable_id": cls.account_receivable.id,
            "property_account_payable_id": cls.account_payable.id,
        })

        # Tax group
        tax_group = cls.env["account.tax.group"].search([
            ("country_id", "=", cls.env.ref("base.ve").id),
        ], limit=1) or cls.env["account.tax.group"].create({
            "name": "IVA",
            "country_id": cls.env.ref("base.ve").id,
        })
        # Tax
        cls.tax_iva16 = cls.env["account.tax"].create({
            "name": "IVA 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.company.id,
            "country_id": cls.env.ref("base.ve").id,
            "tax_group_id": tax_group.id,
        })

        # Journals
        cls.journal_sale = cls.env["account.journal"].create({
            "name": "Test Sale Journal",
            "code": "TSJ",
            "type": "sale",
            "company_id": cls.company.id,
        })
        cls.journal_general = cls.env["account.journal"].create({
            "name": "Test General Journal",
            "code": "TGJ",
            "type": "general",
            "company_id": cls.company.id,
        })

        # Product category with accounts
        cls.product_categ = cls.env["product.category"].create({
            "name": "Test Category",
            "property_account_income_categ_id": cls.account_income.id,
            "property_account_expense_categ_id": cls.account_expense.id,
        })

        # Products
        cls.product_donation = cls.env["product.product"].create({
            "name": "Donation Product",
            "type": "service",
            "list_price": 100.0,
            "categ_id": cls.product_categ.id,
            "taxes_id": [(6, 0, [cls.tax_iva16.id])],
        })
        # Mark product template as donation product
        cls.product_donation.product_tmpl_id.write({
            "is_donation_product": True,
        })

        cls.product_storable = cls.env["product.product"].create({
            "name": "Storable Product",
            "type": "product",
            "list_price": 100.0,
            "categ_id": cls.product_categ.id,
            "taxes_id": [(6, 0, [cls.tax_iva16.id])],
        })

        # Configure company for Venezuelan localization
        cls.company.write({
            "country_id": cls.env.ref("base.ve").id,
            "account_fiscal_country_id": cls.env.ref("base.ve").id,
            "currency_id": cls.currency_vef.id,
            "currency_foreign_id": cls.currency_usd.id,
            "donation_account_id": cls.account_expense.id,
            "account_stock_journal_id": cls.journal_general.id,
        })

        # Warehouses
        cls.warehouse_normal = cls.env["stock.warehouse"].search([
            ("company_id", "=", cls.company.id),
            ("is_donation_warehouse", "=", False),
        ], limit=1)
        if not cls.warehouse_normal:
            cls.warehouse_normal = cls.env["stock.warehouse"].create({
                "name": "Normal Warehouse",
                "code": "NWH",
                "company_id": cls.company.id,
            })
        cls.warehouse_donation = cls.env["stock.warehouse"].create({
            "name": "Donation Warehouse",
            "code": "DWH",
            "company_id": cls.company.id,
            "is_donation_warehouse": True,
        })

        # Picking type donation
        cls.picking_type_donation = cls.env["stock.picking.type"].search([
            ("warehouse_id", "=", cls.warehouse_donation.id),
            ("code", "=", "outgoing"),
        ], limit=1)
        if not cls.picking_type_donation:
            cls.picking_type_donation = cls.env["stock.picking.type"].create({
                "name": "Donation Picking",
                "code": "DON",
                "warehouse_id": cls.warehouse_donation.id,
                "sequence_code": "DON",
                "is_donation_picking_type": True,
            })
        else:
            cls.picking_type_donation.is_donation_picking_type = True

        # Asset data
        cls.asset_account = cls.env["account.account"].create({
            "name": "Asset Account",
            "code": "120001",
            "account_type": "asset_fixed",
            "company_id": cls.company.id,
        })
        cls.asset_journal = cls.env["account.journal"].create({
            "name": "Asset Journal",
            "code": "AST",
            "type": "general",
            "company_id": cls.company.id,
        })
