from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestStockPickingViewNoQuickCreate(TransactionCase):
    """
    Verify that quick creation of products is disabled specifically on the
    move_ids product_id field embedded in the picking form. A plain
    substring count on the whole arch would pass even without this
    field's own xpath, since partner_id already disables quick creation
    independently elsewhere in the same view.
    """

    def test_move_ids_product_field_disables_quick_create(self):
        arch = self.env["stock.picking"].get_view(
            view_id=self.env.ref("stock.view_picking_form").id,
            view_type="form",
        )["arch"]
        doc = etree.fromstring(arch)
        move_ids = doc.xpath("//field[@name='move_ids']")[0]
        product_fields = move_ids.xpath(".//field[@name='product_id']")
        self.assertTrue(
            product_fields,
            "Expected a product_id field inside move_ids.",
        )
        for field in product_fields:
            options = field.get("options") or ""
            self.assertIn(
                "no_quick_create",
                options,
                f"Field product_id (context: {etree.tostring(field)}) "
                "should disable quick creation.",
            )
