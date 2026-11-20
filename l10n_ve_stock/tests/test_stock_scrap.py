from unittest.mock import MagicMock, patch
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockScrapActionValidate(TransactionCase):
    """The scrap rules of the company, on the scrap moves of Odoo 20 (``stock.scrap`` is gone)."""

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

    def _scrap(self, quantity):
        return self.env["stock.move"].with_context(default_is_scrap=True).create({
            "product_id": self.product.id,
            "product_uom_qty": quantity,
            "quantity": quantity,
            "location_id": self.warehouse.lot_stock_id.id,
        })

    def _production(self, produced, scrapped):
        production = MagicMock()
        production.qty_produced = produced
        return (
            patch.object(type(self.env["stock.move"]), "_get_scrap_production", return_value=production),
            patch.object(type(self.env["stock.move"]), "_get_production_scrapped_quantity", return_value=scrapped),
        )

    def test_action_validate_allow_scrap_more_than_available(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = False
        scrap = self._scrap(5)
        scrap.action_scrap()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_not_allow_scrap_check_available(self):
        self.env.company.allow_scrap_more_than_available = False
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = False
        scrap = self._scrap(5)
        scrap.action_scrap()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_not_allow_scrap_insufficient_qty(self):
        self.env.company.allow_scrap_more_than_available = False
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = False
        scrap = self._scrap(99999)
        with self.assertRaises(ValidationError):
            scrap.action_scrap()

    def test_action_validate_not_allow_manufactured_no_production(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self._scrap(5)
        scrap.action_scrap()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_production_no_scraps(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self._scrap(5)
        production, scrapped = self._production(produced=10, scrapped=0)
        with production, scrapped:
            scrap.action_scrap()
        self.assertEqual(scrap.state, "done")

    def test_action_validate_production_exceeds_qty_produced(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self._scrap(15)
        production, scrapped = self._production(produced=10, scrapped=0)
        with production, scrapped, self.assertRaises(ValidationError):
            scrap.action_scrap()

    def test_action_validate_production_sum_exceeds(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self._scrap(6)
        production, scrapped = self._production(produced=10, scrapped=5)
        with production, scrapped, self.assertRaises(ValidationError):
            scrap.action_scrap()

    def test_action_validate_production_within_limit(self):
        self.env.company.allow_scrap_more_than_available = True
        self.env.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap = self._scrap(3)
        production, scrapped = self._production(produced=10, scrapped=5)
        with production, scrapped:
            scrap.action_scrap()
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
