from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPurchaseOrderViewNoQuickCreate(TransactionCase):
    """
    Verify that quick creation of products is disabled on the purchase
    order line product fields (list product_id and the expanded line form
    product_id).
    """

    def test_product_fields_disable_quick_create(self):
        arch = self.env["purchase.order"].get_view(
            view_id=self.env.ref("purchase.purchase_order_form").id,
            view_type="form",
        )["arch"]
        self.assertEqual(
            arch.count("no_quick_create"),
            2,
            "Expected 2 product fields (list product_id and form "
            "product_id) to disable quick creation on the purchase order "
            "form.",
        )
