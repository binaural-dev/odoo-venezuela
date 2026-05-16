from odoo.tests import tagged
from odoo.exceptions import ValidationError
from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'stock_scrap', '-at_install', 'post_install')
class TestStockScrap(TestDonationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_stock = cls.warehouse_normal.lot_stock_id
        cls.env["stock.quant"].create({
            "product_id": cls.product_storable.id,
            "location_id": cls.location_stock.id,
            "quantity": 100.0,
        })

    def test_01_scrap_location_domain(self):
        """Domain changes based on is_donation."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
        })
        self.assertIn("inventory", scrap.scrap_location_domain)
        scrap.is_donation = True
        scrap._compute_scrap_location_domain()
        self.assertIn("is_donation_warehouse", scrap.scrap_location_domain)

    def test_02_scrap_location_id_donation(self):
        """Scrap location is set to a donation warehouse location when is_donation."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
            "is_donation": True,
        })
        scrap._compute_scrap_location_id()
        self.assertTrue(scrap.scrap_location_id)
        self.assertTrue(scrap.scrap_location_id.is_donation_warehouse)

    def test_03_donation_scrap_process(self):
        """Donation scrap creates move and finishes successfully."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 5,
            "location_id": self.location_stock.id,
            "is_donation": True,
            "donation_reason": "Test donation scrap",
        })
        scrap.scrap_location_id = self.warehouse_donation.lot_stock_id
        scrap.do_scrap()
        self.assertEqual(scrap.state, "done")
        self.assertTrue(scrap.move_ids)

    def test_04_normal_scrap_process(self):
        """Normal scrap delegates to super()."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 2,
            "location_id": self.location_stock.id,
            "is_donation": False,
        })
        scrap_location = self.env["stock.location"].search([("scrap_location", "=", True)], limit=1)
        scrap.scrap_location_id = scrap_location.id
        scrap.do_scrap()
        self.assertEqual(scrap.state, "done")

    def test_05_stock_move_prepare_account_move_vals(self):
        """_prepare_account_move_vals propagates donation info from scrap."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
            "is_donation": True,
            "donation_reason": "Reason A",
        })
        scrap.scrap_location_id = self.warehouse_donation.lot_stock_id
        move = self.env["stock.move"].create({
            "name": "Test Move",
            "product_id": self.product_storable.id,
            "product_uom_qty": 1,
            "product_uom": self.product_storable.uom_id.id,
            "location_id": self.location_stock.id,
            "location_dest_id": self.warehouse_donation.lot_stock_id.id,
            "scrap_id": scrap.id,
        })
        vals = move._prepare_account_move_vals(
            credit_account_id=self.account_expense.id,
            debit_account_id=self.account_income.id,
            journal_id=self.journal_general.id,
            qty=1,
            description="Desc",
            svl_id=False,
            cost=10,
        )
        self.assertTrue(vals.get("is_donation"))
        self.assertEqual(vals.get("partner_id"), self.company.partner_id.id)
        self.assertEqual(vals.get("ref"), "Reason A")
        self.assertIn("Reason A", vals.get("ref"))

    def test_06_stock_move_prepare_account_move_vals_no_reason(self):
        """_prepare_account_move_vals with donation but no reason."""
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_storable.id,
            "scrap_qty": 1,
            "location_id": self.location_stock.id,
            "is_donation": True,
        })
        scrap.scrap_location_id = self.warehouse_donation.lot_stock_id
        move = self.env["stock.move"].create({
            "name": "Test Move 2",
            "product_id": self.product_storable.id,
            "product_uom_qty": 1,
            "product_uom": self.product_storable.uom_id.id,
            "location_id": self.location_stock.id,
            "location_dest_id": self.warehouse_donation.lot_stock_id.id,
            "scrap_id": scrap.id,
        })
        vals = move._prepare_account_move_vals(
            credit_account_id=self.account_expense.id,
            debit_account_id=self.account_income.id,
            journal_id=self.journal_general.id,
            qty=1,
            description="Desc",
            svl_id=False,
            cost=10,
        )
        self.assertTrue(vals.get("is_donation"))
        # ref should not contain extra dash when no reason
        self.assertEqual(vals.get("ref"), False)
