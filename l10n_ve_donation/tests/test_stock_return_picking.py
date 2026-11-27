from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'stock_return_picking', '-at_install', 'post_install')
class TestStockReturnPicking(TestDonationCommon):
    """Donations (deliveries and receipts) are not returned, except the
    pickings of a donation sale order."""

    def _done_delivery(self, group=None):
        picking_type = self.picking_type_donation
        product = self.env["product.product"].create({
            "name": "Return Test Product",
            "type": "product",
            "categ_id": self.product_categ.id,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": picking_type.default_location_src_id.id,
            "quantity": 10.0,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "partner_id": self.partner.id,
            "is_donation": True,
            "move_ids": [Command.create({
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": 2,
                "product_uom": product.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "group_id": group.id if group else False,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = 2
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        return picking

    def _return_wizard(self, picking):
        return self.env["stock.return.picking"].with_context(
            active_id=picking.id, active_model="stock.picking"
        ).create({})

    def test_01_donation_delivery_cannot_be_returned(self):
        picking = self._done_delivery()
        self.assertFalse(picking.sale_id)
        wizard = self._return_wizard(picking)
        with self.assertRaises(UserError):
            wizard.create_returns()
        self.assertFalse(self.env["stock.picking"].search([("return_id", "=", picking.id)]))

    def test_02_donation_sale_delivery_can_be_returned(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_donation": True,
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        group = self.env["procurement.group"].create({"name": "Donation Sale Group", "sale_id": order.id})
        picking = self._done_delivery(group=group)
        self.assertTrue(picking.sale_id)
        wizard = self._return_wizard(picking)
        wizard.create_returns()
        self.assertTrue(self.env["stock.picking"].search([("return_id", "=", picking.id)]))

    def test_03_donation_receipt_cannot_be_returned(self):
        receipt_type = self.env["stock.picking.type"].create({
            "name": "Donation Receipt Return Test",
            "code": "incoming",
            "sequence_code": "TDONRCV4",
            "warehouse_id": self.warehouse_donation.id,
            "company_id": self.company.id,
            "is_donation_picking_type": True,
        })
        receipt_type._compute_default_location_src_id()
        receipt_type._compute_default_location_dest_id()
        product = self.env["product.product"].create({
            "name": "Return Receipt Test Product",
            "type": "product",
            "categ_id": self.product_categ.id,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": receipt_type.id,
            "location_id": receipt_type.default_location_src_id.id,
            "location_dest_id": receipt_type.default_location_dest_id.id,
            "partner_id": self.partner.id,
            "is_donation": True,
            "move_ids": [Command.create({
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": 2,
                "product_uom": product.uom_id.id,
                "location_id": receipt_type.default_location_src_id.id,
                "location_dest_id": receipt_type.default_location_dest_id.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.quantity = 2
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.picking_type_code, "incoming")
        with self.assertRaises(UserError):
            self._return_wizard(picking).create_returns()
        self.assertFalse(self.env["stock.picking"].search([("return_id", "=", picking.id)]))

    def test_04_return_button_hidden_for_donations_without_sale(self):
        """The Return button of the picking form is hidden for a donation
        without a sale, on top of the base conditions."""
        arch = self.env["stock.picking"].get_view(
            self.env.ref("stock.view_picking_form").id, "form"
        )["arch"]
        self.assertIn("is_return or (is_donation and not sale_id)", arch)
