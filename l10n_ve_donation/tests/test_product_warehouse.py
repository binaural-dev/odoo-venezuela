from odoo.tests import tagged
from odoo.exceptions import ValidationError
from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'product_warehouse', '-at_install', 'post_install')
class TestProductWarehouse(TestDonationCommon):

    def test_01_unique_donation_product(self):
        """Only one product can be marked as donation product."""
        self.assertTrue(self.product_donation.product_tmpl_id.is_donation_product)
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "Another Donation Product",
                "is_donation_product": True,
            })

    def test_02_warehouse_unique_donation(self):
        """Only one donation warehouse per company."""
        with self.assertRaises(ValidationError):
            self.env["stock.warehouse"].create({
                "name": "Another Donation Warehouse",
                "code": "ADW",
                "company_id": self.company.id,
                "is_donation_warehouse": True,
            })

    def test_03_location_donation_compute(self):
        """Location inherits donation flag from warehouse."""
        location = self.warehouse_donation.lot_stock_id
        self.assertTrue(location.is_donation_warehouse)
        normal_location = self.warehouse_normal.lot_stock_id
        self.assertFalse(normal_location.is_donation_warehouse)

    def test_04_location_get_warehouse(self):
        """get_warehouse returns the correct warehouse."""
        location = self.warehouse_donation.lot_stock_id
        warehouse = location.get_warehouse()
        self.assertEqual(warehouse, self.warehouse_donation)
        # New record without id
        new_loc = self.env["stock.location"].new({"name": "Fake"})
        self.assertFalse(new_loc.get_warehouse())

    def test_05_picking_type_donation_must_be_outgoing(self):
        """Donation picking type must have code outgoing."""
        with self.assertRaises(ValidationError):
            self.env["stock.picking.type"].create({
                "name": "Bad Donation Picking",
                "code": "incoming",
                "sequence_code": "BAD",
                "is_donation_picking_type": True,
            })

    def test_06_warehouse_readonly_compute(self):
        """Readonly field mirrors is_donation_warehouse."""
        self.assertTrue(self.warehouse_donation.readonly_is_donation_warehouse)
        self.assertFalse(self.warehouse_normal.readonly_is_donation_warehouse)
