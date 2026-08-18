from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestStockPickingViewNoQuickCreate(TransactionCase):
    """
    Verify that quick creation of products is disabled on the stock move
    line product_id field embedded in the picking form.
    """

    def test_product_field_disables_quick_create(self):
        arch = self.env["stock.picking"].get_view(
            view_id=self.env.ref("stock.view_picking_form").id,
            view_type="form",
        )["arch"]
        self.assertGreaterEqual(
            arch.count("no_quick_create"),
            1,
            "Expected the move_ids product_id field to disable quick "
            "creation on the picking form.",
        )
