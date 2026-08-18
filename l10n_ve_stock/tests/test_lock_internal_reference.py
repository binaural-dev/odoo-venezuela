from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestLockInternalReferenceOnMoves(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create({"name": "Cliente Test"})
        self.location_src = self.env["stock.location"].create(
            {"name": "Origen Test", "usage": "internal"}
        )
        self.location_dest = self.env["stock.location"].create(
            {"name": "Destino Test", "usage": "internal"}
        )

    def _create_product(self, default_code):
        return self.env["product.product"].create(
            {
                "name": "Producto Test",
                "default_code": default_code,
                "type": "consu",
                "is_storable": True,
            }
        )

    def test_create_product_with_default_code(self):
        product = self._create_product("REF001")
        self.assertEqual(product.default_code, "REF001")

    def test_write_default_code_without_moves(self):
        product = self._create_product("REF002")
        product.write({"default_code": "REF002-B"})
        self.assertEqual(product.default_code, "REF002-B")

    def _create_done_move(self, product):
        move = self.env["stock.move"].create(
            {
                "product_id": product.id,
                "product_uom_qty": 1,
                "product_uom": product.uom_id.id,
                "location_id": self.location_src.id,
                "location_dest_id": self.location_dest.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        move.quantity = 1
        move.picked = True
        move._action_done()
        return move

    def test_write_default_code_blocked_with_done_stock_move(self):
        product = self._create_product("REF003")
        self._create_done_move(product)
        with self.assertRaises(ValidationError):
            product.write({"default_code": "REF003-B"})

    def test_write_default_code_allowed_when_lock_disabled(self):
        product = self._create_product("REF004")
        product.lock_internal_reference_on_moves = False
        self._create_done_move(product)
        product.write({"default_code": "REF004-B"})
        self.assertEqual(product.default_code, "REF004-B")

    def test_write_default_code_allowed_when_not_storable(self):
        product = self.env["product.product"].create(
            {
                "name": "Producto No Almacenable",
                "default_code": "REF005",
                "type": "consu",
                "is_storable": False,
            }
        )
        self._create_done_move(product)
        product.write({"default_code": "REF005-B"})
        self.assertEqual(product.default_code, "REF005-B")

