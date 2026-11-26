# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import Form, tagged

from .common import StockAccountTestCommon


@tagged("post_install", "-at_install")
class TestPickingLocation(StockAccountTestCommon):
    """Source location of transfers and their moves.

    The transfer's source location is computed from its operation type and
    partner and, for consignment sales, from the customer's consignment
    location. Editing a move from the transfer form must not recompute the
    move's own source location.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.location_stock = cls.env.ref("stock.stock_location_stock")
        cls.location_suppliers = cls.env.ref("stock.stock_location_suppliers")

        cls.partner = cls.env["res.partner"].create({
            "name": "Location Customer",
            "default_document": "dispatch_guide",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Location Product",
            "type": "consu",
            "is_storable": True,
            "lst_price": 100.0,
        })

        cls.consignation_wh = cls.env["stock.warehouse"].create({
            "name": "Location Consignation WH",
            "code": "LCWH",
            "is_consignation_warehouse": True,
        })
        cls.consignation_location = cls.env["stock.location"].create({
            "name": "Customer Consignation",
            "usage": "internal",
            "location_id": cls.consignation_wh.view_location_id.id,
            "partner_id": cls.partner.id,
        })
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.consignation_location, 10)

    def _consignation_sale(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.consignation_wh.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 5,
                "tax_ids": [Command.clear()],
            })],
        })

    def test_edit_move_quantity_keeps_move_source_location(self):
        """Editing the quantity of a move from the transfer form keeps the
        move's source location when it differs from the transfer's, as for
        a subcontracting receipt (the move comes from the subcontracting
        location, the transfer from the vendor)."""
        vendor_sublocation = self.env["stock.location"].create({
            "name": "Vendor Sublocation",
            "usage": "supplier",
            "location_id": self.location_suppliers.id,
        })
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": self.picking_type_in.id,
            "location_id": self.location_suppliers.id,
            "location_dest_id": self.location_stock.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 10,
                "location_id": vendor_sublocation.id,
                "location_dest_id": self.location_stock.id,
            })],
        })
        picking.action_confirm()
        move = picking.move_ids
        self.assertEqual(move.location_id, vendor_sublocation)

        with Form(picking) as picking_form:
            with picking_form.move_ids.edit(0) as move_form:
                move_form.quantity = 4

        self.assertEqual(move.quantity, 4)
        self.assertEqual(move.location_id, vendor_sublocation)
        self.assertEqual(picking.location_id, self.location_suppliers)

    def test_new_picking_takes_locations_from_operation_type(self):
        picking_form = Form(self.env["stock.picking"])
        picking_form.picking_type_id = self.picking_type_out
        picking_form.partner_id = self.partner
        self.assertEqual(picking_form.location_id, self.picking_type_out.default_location_src_id)
        self.assertEqual(picking_form.location_dest_id, self.picking_type_out.default_location_dest_id)

    def test_new_picking_keeps_location_when_sale_is_set_afterwards(self):
        """The source location is only filled while empty: linking a
        consignment sale after choosing the operation type keeps the
        location of the operation type."""
        sale = self._consignation_sale()
        picking_form = Form(self.env["stock.picking"])
        picking_form.picking_type_id = self.picking_type_out
        picking_form.partner_id = self.partner
        picking_form.sale_id = sale
        self.assertEqual(picking_form.location_id, self.picking_type_out.default_location_src_id)

    def test_consignation_sale_delivery_keeps_locations_when_edited(self):
        """The delivery of a confirmed consignment sale leaves from the
        consignment warehouse and keeps its locations when a move is edited
        from the form."""
        sale = self._consignation_sale()
        sale.action_confirm()
        picking = sale.picking_ids
        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.sale_id, sale)
        self.assertEqual(picking.location_id, self.consignation_wh.lot_stock_id)
        self.assertEqual(picking.move_ids.location_id, self.consignation_wh.lot_stock_id)

        with Form(picking) as picking_form:
            with picking_form.move_ids.edit(0) as move_form:
                move_form.quantity = 2

        self.assertEqual(picking.move_ids.quantity, 2)
        self.assertEqual(picking.location_id, self.consignation_wh.lot_stock_id)
        self.assertEqual(picking.move_ids.location_id, self.consignation_wh.lot_stock_id)

    def test_new_consignation_picking_takes_customer_consignation_location(self):
        """A new delivery linked to a consignment sale before choosing the
        operation type leaves from the customer's location in the
        consignment warehouse."""
        sale = self._consignation_sale()
        self.assertTrue(sale.is_consignation)
        picking_form = Form(self.env["stock.picking"])
        picking_form.partner_id = self.partner
        picking_form.sale_id = sale
        picking_form.picking_type_id = self.picking_type_out
        self.assertEqual(picking_form.location_id, self.consignation_location)
        picking = picking_form.save()
        self.assertEqual(picking.location_id, self.consignation_location)

    def test_new_consignation_picking_ignores_customer_location_outside_consignation(self):
        """A location of the customer outside the consignment warehouse is not
        a consignment location: without one inside, the delivery takes the
        location of its operation type."""
        customer = self.env["res.partner"].create({"name": "Customer Without Consignation"})
        self.env["stock.location"].create({
            "name": "Customer Location Outside Consignation",
            "usage": "internal",
            "location_id": self.location_stock.id,
            "partner_id": customer.id,
        })
        sale = self.env["sale.order"].create({
            "partner_id": customer.id,
            "warehouse_id": self.consignation_wh.id,
        })
        self.assertTrue(sale.is_consignation)
        picking_form = Form(self.env["stock.picking"])
        picking_form.partner_id = customer
        picking_form.sale_id = sale
        picking_form.picking_type_id = self.picking_type_out
        self.assertEqual(picking_form.location_id, self.picking_type_out.default_location_src_id)

    def test_new_picking_keeps_source_location_chosen_before_operation_type(self):
        """Filling the destination location from the operation type keeps the
        source location already chosen."""
        picking_form = Form(self.env["stock.picking"])
        picking_form.partner_id = self.partner
        picking_form.location_id = self.consignation_location
        picking_form.picking_type_id = self.picking_type_out
        self.assertEqual(picking_form.location_id, self.consignation_location)
        self.assertEqual(picking_form.location_dest_id, self.picking_type_out.default_location_dest_id)
