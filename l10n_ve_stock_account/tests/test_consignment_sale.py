from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .common import StockAccountCommon


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestConsignmentSale(StockAccountCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["stock.warehouse"].search([("is_consignation_warehouse", "=", True)]).write(
            {"is_consignation_warehouse": False}
        )
        cls.main_warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id), ("is_consignation_warehouse", "=", False)], limit=1
        )
        cls.consignation_warehouse = cls.env["stock.warehouse"].create(
            {
                "name": "Consignación",
                "code": "CNS",
                "partner_id": cls.partner.id,
                "is_consignation_warehouse": True,
            }
        )
        cls.customer_location = cls.env["stock.location"].create(
            {
                "name": "Ubicación cliente",
                "usage": "internal",
                "location_id": cls.consignation_warehouse.view_location_id.id,
                "partner_id": cls.partner.id,
            }
        )
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.customer_location, 5)

    def test_single_consignation_warehouse(self):
        with self.assertRaises(ValidationError):
            self.env["stock.warehouse"].create(
                {"name": "Segunda", "code": "CN2", "is_consignation_warehouse": True}
            )
        self.assertTrue(self.consignation_warehouse.readonly_is_consignation_warehouse)

    def test_consignation_locations(self):
        self.assertTrue(self.customer_location.is_consignation_warehouse)
        self.assertEqual(self.customer_location.get_warehouse(), self.consignation_warehouse)
        self.assertFalse(self.env["stock.location"].new({"name": "Nueva"}).get_warehouse())

        with self.assertRaises(ValidationError):
            self.env["stock.location"].create(
                {
                    "name": "Vista",
                    "usage": "view",
                    "location_id": self.consignation_warehouse.view_location_id.id,
                }
            )

        self.consignation_warehouse.partner_id = False
        with self.assertRaises(ValidationError):
            self.customer_location.write({"partner_id": False})

    def test_consignation_sale_order(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "warehouse_id": self.consignation_warehouse.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 2})],
            }
        )
        self.assertTrue(order.is_consignation)
        self.assertEqual(order.document, "invoice")
        self.assertTrue(order.show_is_subcontracting)


    def test_consignation_sale_without_stock(self):
        other_product = self.env["product.product"].create(
            {"name": "Sin consignación", "type": "product", "list_price": 10}
        )
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "warehouse_id": self.consignation_warehouse.id,
                    "order_line": [(0, 0, {"product_id": other_product.id, "product_uom_qty": 1})],
                }
            )
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create(
                {
                    "partner_id": self.partner.id,
                    "warehouse_id": self.consignation_warehouse.id,
                    "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 50})],
                }
            )

    def test_consignation_onchange(self):
        with Form(self.env["sale.order"]) as order_form:
            order_form.partner_id = self.partner
            order_form.is_consignation = True
            self.assertEqual(order_form.warehouse_id, self.consignation_warehouse)
            order_form.is_consignation = False
            self.assertEqual(order_form.warehouse_id, self.main_warehouse)

        self.consignation_warehouse.is_consignation_warehouse = False
        order = self.env["sale.order"].new({"partner_id": self.partner.id, "is_consignation": True})
        with self.assertRaises(ValidationError):
            order._onchange_is_consignation()

    def test_consignment_picking_takes_partner_from_location(self):
        picking = self.create_picking("consignment", operation_code="internal")
        picking.write({"location_dest_id": self.customer_location.id, "is_dispatch_guide": True})

        self.assertTrue(picking.partner_required)
        self.assertEqual(picking.partner_id, self.partner)
        self.assertTrue(picking.show_create_invoice_internal is False or picking.state != "done")

        picking._change_required_partner_id()
        self.assertEqual(picking.partner_id, self.partner)

        internal = self.create_picking("transfer", operation_code="internal")
        internal.location_dest_id = self.customer_location
        internal._compute_allowed_reason_ids()
        self.assertEqual(internal.transfer_reason_id, self.env.ref("l10n_ve_stock_account.transfer_reason_consignment"))
        self.assertTrue(internal.is_consignment_readonly)

    def test_sale_document_defaults(self):
        self.partner.default_document = "dispatch_guide"
        order = self.env["sale.order"].with_context(default_partner_id=self.partner.id).create(
            {"partner_id": self.partner.id}
        )
        self.assertEqual(order.document, "dispatch_guide")
        self.assertEqual(self.env["sale.order"]._default_document(), "invoice")

        order.partner_id = False
        order._onchange_partner_id()
        self.assertEqual(order.document, "invoice")
        order.partner_id = self.partner
        order._onchange_partner_id()
        self.assertEqual(order.document, "dispatch_guide")

        order.is_subcontracting = True
        order.document = "invoice"
        order._onchange_document_subcontracting()
        self.assertFalse(order.is_subcontracting)

        self.company.is_subcontracting = True
        order.document = "dispatch_guide"
        order._compute_show_is_subcontracting()
        self.assertFalse(order.show_is_subcontracting)

    def test_new_picking_location_defaults(self):
        picking_type = self.main_warehouse.out_type_id
        picking = self.env["stock.picking"].new({"picking_type_id": picking_type.id})

        source = self.main_warehouse.lot_stock_id
        picking.location_id = source
        picking.location_dest_id = False
        picking._compute_location_id()
        self.assertEqual(picking.location_id, source)
