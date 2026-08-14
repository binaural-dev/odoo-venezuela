# -*- coding: utf-8 -*-
import logging
from odoo.tests import TransactionCase, tagged
from odoo import Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "test_stock_move_coverage")
class TestStockMoveCoverage(TransactionCase):
    """Tests to cover branches in stock.move that were previously uncovered."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_usd.active = True
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.currency_vef.active = True

        cls.company = cls.env.company
        cls.company.write({
            "currency_id": cls.currency_vef.id,
            "foreign_currency_id": cls.currency_usd.id,
        })

        cls.partner = cls.env["res.partner"].create({"name": "Move Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Move Product",
            "type": "consu",
            "lst_price": 100.0,
        })

        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.location_src = cls.env.ref("stock.stock_location_stock")
        cls.location_dest = cls.env.ref("stock.stock_location_customers")

    def test_get_line_values_without_sale_line(self):
        """_get_line_values early return when there is no sale_line_id."""
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_out.id,
            "location_id": self.location_src.id,
            "location_dest_id": self.location_dest.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "location_id": self.location_src.id,
                "location_dest_id": self.location_dest.id,
            })],
        })
        picking.action_confirm()
        move = picking.move_ids[0]
        vals = move._get_line_values()
        self.assertEqual(vals["quantity"], 1.0)
        self.assertEqual(vals["price_unit"], 0.0)
        self.assertEqual(vals["subtotal"], 0.0)

    def test_price_unit_ves_for_dispatch_guide_without_sale_line(self):
        """price_unit_ves_for_dispatch_guide returns 0.0 when no sale_line_id."""
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_out.id,
            "location_id": self.location_src.id,
            "location_dest_id": self.location_dest.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "location_id": self.location_src.id,
                "location_dest_id": self.location_dest.id,
            })],
        })
        picking.action_confirm()
        move = picking.move_ids[0]
        self.assertEqual(move.price_unit_ves_for_dispatch_guide(), 0.0)
