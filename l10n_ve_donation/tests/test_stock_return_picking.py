from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'stock_return_picking', '-at_install', 'post_install')
class TestStockReturnPicking(TestDonationCommon):
    """Donations (deliveries and receipts) are not returned, except the
    pickings of a donation sale order.

    The wizard is exercised through its real entry point
    (`action_create_returns`, which calls `_create_return`), with a non-zero
    quantity on a line, so that the refusal is proven to come from the
    donation rule and not from the wizard having nothing to return."""

    def _storable_product(self, name):
        return self.env["product.product"].create({
            "name": name,
            "type": "consu",
            "is_storable": True,
            "categ_id": self.product_categ.id,
        })

    def _validate(self, picking):
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({"quantity": 2, "picked": True})
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def _done_donation_delivery(self):
        """Done donation delivery from the Donations menu (no sale order)."""
        product = self._storable_product("Return Test Product")
        picking = self._create_donation_picking(
            quantity=2.0, partner=self.partner, product=product, validate=True
        )
        self.assertEqual(picking.state, "done")
        self.assertTrue(picking.is_donation)
        self.assertFalse(picking.sale_id)
        return picking

    def _done_donation_sale_delivery(self):
        """Done delivery to the customer location of a donation sale order."""
        product = self._storable_product("Return Sale Test Product")
        self._create_stock(product, 10.0, self.warehouse_normal.lot_stock_id)
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_donation": True,
            "manually_set_rate": True,
            "foreign_rate": 1.0,
            "foreign_inverse_rate": 1.0,
        })
        picking_type = self.warehouse_normal.out_type_id
        customers = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": customers.id,
            "partner_id": self.partner.id,
            "sale_id": order.id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
                "product_uom": product.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": customers.id,
            })],
        })
        self._validate(picking)
        return picking

    def _return_wizard(self, picking, quantity=2.0):
        wizard = self.env["stock.return.picking"].with_context(
            active_id=picking.id, active_model="stock.picking"
        ).create({})
        wizard.product_return_moves.write({"quantity": quantity})
        return wizard

    def _returns_of(self, picking):
        return self.env["stock.picking"].search([("return_id", "=", picking.id)])

    def test_01_donation_delivery_cannot_be_returned(self):
        picking = self._done_donation_delivery()
        wizard = self._return_wizard(picking)
        with self.assertRaisesRegex(UserError, "donations are not returned"):
            wizard.action_create_returns()
        self.assertFalse(self._returns_of(picking))

    def test_02_donation_sale_delivery_can_be_returned(self):
        picking = self._done_donation_sale_delivery()
        self.assertTrue(picking.sale_id)
        self.assertTrue(picking.is_donation)
        wizard = self._return_wizard(picking)
        wizard.action_create_returns()
        self.assertTrue(self._returns_of(picking))

    def test_03_donation_receipt_cannot_be_returned(self):
        receipt_type = self.env["stock.picking.type"].create({
            "name": "Donation Receipt Return Test",
            "code": "incoming",
            "sequence_code": "TDONRCV4",
            "warehouse_id": self.warehouse_donation.id,
            "company_id": self.company.id,
            "is_donation_picking_type": True,
        })
        product = self._storable_product("Return Receipt Test Product")
        picking = self.env["stock.picking"].create({
            "picking_type_id": receipt_type.id,
            "location_id": receipt_type.default_location_src_id.id,
            "location_dest_id": receipt_type.default_location_dest_id.id,
            "partner_id": self.partner.id,
            "is_donation": True,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
                "product_uom": product.uom_id.id,
                "location_id": receipt_type.default_location_src_id.id,
                "location_dest_id": receipt_type.default_location_dest_id.id,
            })],
        })
        self._validate(picking)
        self.assertEqual(picking.picking_type_code, "incoming")
        wizard = self._return_wizard(picking)
        with self.assertRaisesRegex(UserError, "donations are not returned"):
            wizard.action_create_returns()
        self.assertFalse(self._returns_of(picking))

    def test_04_return_button_hidden_for_donations_without_sale(self):
        """The Return button of the picking form is hidden for a donation
        without a sale, on top of the base conditions."""
        arch = self.env["stock.picking"].get_view(
            self.env.ref("stock.view_picking_form").id, "form"
        )["arch"]
        self.assertIn("is_return or (is_donation and not sale_id)", arch)

    def test_05_return_of_a_donation_sale_delivery_does_not_keep_the_donation_reason(self):
        """`copy()` would take the 'Donation' transfer reason of the
        delivery, which the inventory book counts as a withdrawal whatever
        the direction of the move."""
        picking = self._done_donation_sale_delivery()
        donation_reason = self.env.ref("l10n_ve_stock_account.transfer_reason_donation")
        picking.transfer_reason_id = donation_reason
        self.assertEqual(picking.transfer_reason_id, donation_reason)

        self._return_wizard(picking).action_create_returns()

        return_picking = self._returns_of(picking)
        self.assertTrue(return_picking)
        self.assertNotEqual(return_picking.transfer_reason_id, donation_reason)
        self.assertEqual(picking.transfer_reason_id, donation_reason)

    def test_06_return_of_a_regular_delivery_keeps_its_reason(self):
        """Only the donation pickings drop their reason."""
        product = self._storable_product("Return Regular Test Product")
        self._create_stock(product, 10.0, self.warehouse_normal.lot_stock_id)
        picking_type = self.warehouse_normal.out_type_id
        customers = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": customers.id,
            "partner_id": self.partner.id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
                "product_uom": product.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": customers.id,
            })],
        })
        self._validate(picking)
        self.assertFalse(picking.is_donation)
        sale_reason = self.env.ref("l10n_ve_stock_account.transfer_reason_sale")
        picking.transfer_reason_id = sale_reason

        self._return_wizard(picking).action_create_returns()

        return_picking = self._returns_of(picking)
        self.assertTrue(return_picking)
        self.assertEqual(return_picking.transfer_reason_id, sale_reason)

