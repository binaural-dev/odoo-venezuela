from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'stock_picking_type', '-at_install', 'post_install')
class TestStockPickingType(TestDonationCommon):

    def test_05_picking_type_donation_must_be_incoming_or_outgoing(self):
        """Donation picking type must have code incoming or outgoing.

        `is_donation_picking_type` is a shared flag: `l10n_ve_donation` uses
        it for its outgoing donation delivery, `higea_donation` reuses the
        SAME flag for its incoming donation receipt -- so both codes must be
        accepted, while any other code (ej. 'internal') must still fail."""
        donation_incoming = self.env["stock.picking.type"].create({
            "name": "Donation Receipt",
            "code": "incoming",
            "sequence_code": "DONIN",
            "is_donation_picking_type": True,
        })
        self.assertTrue(donation_incoming.is_donation_picking_type)

        donation_outgoing = self.env["stock.picking.type"].create({
            "name": "Donation Delivery",
            "code": "outgoing",
            "sequence_code": "DONOUT",
            "warehouse_id": self.warehouse_donation.id,
            "default_location_dest_id": self.location_donation.id,
            "is_donation_picking_type": True,
        })
        self.assertTrue(donation_outgoing.is_donation_picking_type)

        with self.assertRaises(ValidationError):
            self.env["stock.picking.type"].create({
                "name": "Bad Donation Picking",
                "code": "internal",
                "sequence_code": "BAD",
                "is_donation_picking_type": True,
            })

    def _create_outgoing_type(self, sequence_code, **vals):
        return self.env["stock.picking.type"].create({
            "name": f"Donation Delivery {sequence_code}",
            "code": "outgoing",
            "sequence_code": sequence_code,
            "is_donation_picking_type": True,
            **vals,
        })

    def test_08_outgoing_donation_type_requires_donation_warehouse(self):
        """An outgoing donation type without warehouse or in a warehouse that
        is not the donation one is rejected; an incoming one is not affected."""
        with self.assertRaises(ValidationError):
            self._create_outgoing_type("DONNOWH")
        with self.assertRaises(ValidationError):
            self._create_outgoing_type(
                "DONNORM",
                warehouse_id=self.warehouse_normal.id,
                default_location_dest_id=self.location_donation.id,
            )
        normal_type = self.env["stock.picking.type"].search([
            ("warehouse_id", "=", self.warehouse_normal.id),
            ("code", "=", "outgoing"),
        ], limit=1)
        with self.assertRaises(ValidationError):
            normal_type.is_donation_picking_type = True
        incoming = self.env["stock.picking.type"].create({
            "name": "Donation Receipt Normal Warehouse",
            "code": "incoming",
            "sequence_code": "DONRNW",
            "warehouse_id": self.warehouse_normal.id,
            "is_donation_picking_type": True,
        })
        self.assertTrue(incoming.is_donation_picking_type)

    def test_09_outgoing_donation_type_destination_must_be_inventory(self):
        """The default destination of an outgoing donation type must be an
        `inventory` location (the default one, Customers, is rejected)."""
        customers = self.env.ref("stock.stock_location_customers")
        with self.assertRaises(ValidationError):
            self._create_outgoing_type(
                "DONCUST",
                warehouse_id=self.warehouse_donation.id,
                default_location_dest_id=customers.id,
            )
        with self.assertRaises(ValidationError):
            self._create_outgoing_type("DONDEF", warehouse_id=self.warehouse_donation.id)
        with self.assertRaises(ValidationError):
            self.picking_type_donation.default_location_dest_id = customers

    def test_10_outgoing_donation_type_destination_does_not_need_account(self):
        """The incoming valuation account is not checked on the type: the
        delivery validation requires it (only for real_time products)."""
        no_account = self.env["stock.location"].create({
            "name": "Inventory Loss Without Account",
            "usage": "inventory",
            "location_id": self.warehouse_donation.view_location_id.id,
            "valuation_in_account_id": False,
        })
        picking_type = self._create_outgoing_type(
            "DONNOACC",
            warehouse_id=self.warehouse_donation.id,
            default_location_dest_id=no_account.id,
        )
        self.assertEqual(picking_type.default_location_dest_id, no_account)
        self.picking_type_donation.default_location_dest_id = no_account
        self.assertEqual(self.picking_type_donation.default_location_dest_id, no_account)

    def test_11_outgoing_donation_type_destination_can_be_in_another_warehouse(self):
        """The destination is not required to belong to the warehouse of the
        type: any `inventory` location with account is accepted."""
        other_location = self.env["stock.location"].create({
            "name": "Other Warehouse Inventory Loss",
            "usage": "inventory",
            "location_id": self.warehouse_normal.view_location_id.id,
            "valuation_in_account_id": self.account_expense.id,
        })
        picking_type = self._create_outgoing_type(
            "DONOTH",
            warehouse_id=self.warehouse_donation.id,
            default_location_dest_id=other_location.id,
        )
        self.assertEqual(picking_type.default_location_dest_id, other_location)

    def test_12_outgoing_donation_type_valid_and_not_flagged_types_free(self):
        """A well configured type is accepted, and a type without the
        donation flag can use any destination."""
        valid = self._create_outgoing_type(
            "DONOK",
            warehouse_id=self.warehouse_donation.id,
            default_location_dest_id=self.location_donation.id,
        )
        self.assertEqual(valid.default_location_dest_id, self.location_donation)
        plain = self.env["stock.picking.type"].create({
            "name": "Plain Delivery",
            "code": "outgoing",
            "sequence_code": "PLAINOUT",
            "warehouse_id": self.warehouse_normal.id,
            "default_location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        self.assertFalse(plain.is_donation_picking_type)
