from odoo import Command

from odoo.addons.l10n_ve_stock_account.tests.common import StockAccountTestCommon


class TestDonationCommon(StockAccountTestCommon):
    """Fixtures shared by the tests of `l10n_ve_donation`.

    The fiscal/currency setup (company, VEF/USD, rate, taxes) comes from
    `StockAccountTestCommon`. This class adds the donation configuration:
    accounts, journals, the donation warehouse with its `inventory`
    destination (and its valuation account), a dedicated outgoing operation
    type, and a storable product with automated (real_time) valuation.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company
        company_ids = [Command.set([company.id])]

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
            "country_id": cls.env.ref("base.ve").id,
            "email": "test@example.com",
        })

        # Accounts
        cls.account_income = cls.env["account.account"].create({
            "name": "Income Test",
            "code": "DON410001",
            "account_type": "income",
            "company_ids": company_ids,
        })
        cls.account_expense = cls.env["account.account"].create({
            "name": "Expense Test",
            "code": "DON610001",
            "account_type": "expense",
            "company_ids": company_ids,
        })
        cls.account_stock = cls.env["account.account"].create({
            "name": "Stock Valuation Test",
            "code": "DON110101",
            "account_type": "asset_current",
            "company_ids": company_ids,
        })
        cls.account_receivable = cls.env["account.account"].search(
            [("account_type", "=", "asset_receivable"), ("company_ids", "in", company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Receivable Test",
            "code": "DON110001",
            "account_type": "asset_receivable",
            "company_ids": company_ids,
        })
        if not cls.company.partner_id.property_account_receivable_id:
            cls.company.partner_id.property_account_receivable_id = cls.account_receivable

        # Journals
        cls.journal_sale = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
        ) or cls.env["account.journal"].create({
            "name": "Test Sale Journal",
            "code": "TSJ",
            "type": "sale",
            "company_id": company.id,
        })
        cls.journal_general = cls.env["account.journal"].create({
            "name": "Test Stock Journal",
            "code": "TGJ",
            "type": "general",
            "company_id": company.id,
        })
        company.write({
            "donation_account_id": cls.account_expense.id,
            "account_stock_journal_id": cls.journal_general.id,
        })

        # Product category with automated valuation
        cls.product_categ = cls.env["product.category"].create({
            "name": "Donation Test Category",
            "property_account_income_categ_id": cls.account_income.id,
            "property_account_expense_categ_id": cls.account_expense.id,
            "property_valuation": "real_time",
            "property_cost_method": "standard",
            "property_stock_valuation_account_id": cls.account_stock.id,
            "property_stock_journal": cls.journal_general.id,
        })

        # Donation product (service) used by the credit notes
        cls.product_donation = cls.env["product.product"].create({
            "name": "Donation Product",
            "type": "service",
            "list_price": 100.0,
            "categ_id": cls.product_categ.id,
        })
        cls.product_donation.product_tmpl_id.is_donation_product = True

        # Storable product with real_time valuation
        cls.product_storable = cls.env["product.product"].create({
            "name": "Storable Product",
            "type": "consu",
            "is_storable": True,
            "list_price": 100.0,
            "standard_price": 15.0,
            "categ_id": cls.product_categ.id,
        })

        # Warehouses
        cls.warehouse_normal = cls.env["stock.warehouse"].search(
            [("company_id", "=", company.id), ("is_donation_warehouse", "=", False)],
            limit=1,
        )
        cls.warehouse_donation = cls.env["stock.warehouse"].create({
            "name": "Donation Warehouse",
            "code": "DWH",
            "company_id": company.id,
            "is_donation_warehouse": True,
        })

        # Donation destination: an `inventory` location of the donation
        # warehouse with its valuation account set.
        cls.location_donation = cls.env["stock.location"].create({
            "name": "Donations",
            "usage": "inventory",
            "location_id": cls.warehouse_donation.view_location_id.id,
            "company_id": company.id,
            "valuation_account_id": cls.account_expense.id,
        })

        # A dedicated outgoing type (as the real "Donations" type of a
        # donation warehouse), not the standard "Delivery Orders" type.
        cls.picking_type_donation = cls.env["stock.picking.type"].create({
            "name": "Donation Picking",
            "code": "outgoing",
            "warehouse_id": cls.warehouse_donation.id,
            "sequence_code": "DWHDON",
            "default_location_src_id": cls.warehouse_donation.lot_stock_id.id,
            "default_location_dest_id": cls.location_donation.id,
            "is_donation_picking_type": True,
        })

    @classmethod
    def _create_stock(cls, product, quantity, location):
        cls.env["stock.quant"]._update_available_quantity(product, location, quantity)

    def _create_donation_picking(self, quantity=1.0, partner=None, reason=None,
                                 product=None, validate=False):
        """Outgoing donation delivery created as the Donations menu does
        (`is_donation` set, no sale order)."""
        product = product or self.product_storable
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_donation.id,
            "location_id": self.picking_type_donation.default_location_src_id.id,
            "location_dest_id": self.picking_type_donation.default_location_dest_id.id,
            "partner_id": partner.id if partner else False,
            "donation_reason": reason,
            "is_donation": True,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": quantity,
                "product_uom": product.uom_id.id,
                "location_id": self.picking_type_donation.default_location_src_id.id,
                "location_dest_id": self.picking_type_donation.default_location_dest_id.id,
            })],
        })
        if validate:
            self._create_stock(product, quantity, picking.location_id)
            picking.action_confirm()
            picking.action_assign()
            picking.move_ids.write({"quantity": quantity, "picked": True})
            picking.button_validate()
        return picking
