from unittest.mock import MagicMock, patch, PropertyMock
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockScrapActionValidate(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.product = self.env["product.product"].create({
            "name": "Scrap Test Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": self.product.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "quantity": 50,
        })

    def test_action_validate_allow_scrap_more_than_available(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = False
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 5,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        scrap.action_validate()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_not_allow_scrap_check_available(self):
        self.env.company.allow_scrap_more_than_available = False
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = False
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 5,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        scrap.action_validate()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_not_allow_scrap_insufficient_qty(self):
        self.env.company.allow_scrap_more_than_available = False
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = False
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 99999,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        with self.assertRaises(ValidationError):
            scrap.action_validate()

    def test_action_validate_not_allow_manufactured_no_production(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 5,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        scrap.action_validate()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_production_no_scraps(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 5,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        mock_production = MagicMock()
        mock_production.qty_produced = 10
        mock_production.scrap_ids = False
        with patch.object(type(scrap), 'production_id', mock_production, create=True):
            scrap.action_validate()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_production_exceeds_qty_produced(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 15,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        done_scrap = MagicMock()
        done_scrap.state = "done"
        done_scrap.scrap_qty = 0
        mock_scraps = MagicMock()
        mock_scraps.__bool__ = lambda self: True
        mock_scraps.filtered = MagicMock(return_value=[done_scrap])
        mock_production = MagicMock()
        mock_production.qty_produced = 10
        mock_production.scrap_ids = mock_scraps
        with patch.object(type(scrap), 'production_id', mock_production, create=True):
            with self.assertRaises(ValidationError):
                scrap.action_validate()

    def test_action_validate_production_sum_exceeds(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 6,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        done_item = MagicMock()
        done_item.state = "done"
        done_item.scrap_qty = 5
        mock_scraps = MagicMock()
        mock_scraps.__bool__ = lambda self: True
        mock_scraps.filtered = MagicMock(return_value=[done_item])
        mock_production = MagicMock()
        mock_production.qty_produced = 10
        mock_production.scrap_ids = mock_scraps
        with patch.object(type(scrap), 'production_id', mock_production, create=True):
            with self.assertRaises(ValidationError):
                scrap.action_validate()

    def test_action_validate_production_within_limit(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product.id,
            "scrap_qty": 3,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        done_item = MagicMock()
        done_item.state = "done"
        done_item.scrap_qty = 5
        mock_scraps = MagicMock()
        mock_scraps.__bool__ = lambda self: True
        mock_scraps.filtered = MagicMock(return_value=[done_item])
        mock_production = MagicMock()
        mock_production.qty_produced = 10
        mock_production.scrap_ids = mock_scraps
        with patch.object(type(scrap), 'production_id', mock_production, create=True):
            scrap.action_validate()
        self.assertEqual(scrap.state, "done")


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockScrapChangeWeight(TransactionCase):
    def test_change_weight_field(self):
        self.env.company.change_weight = True
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        self.assertTrue(picking.change_weight)
