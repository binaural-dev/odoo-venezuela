from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSaleOrderViewNoQuickCreate(TransactionCase):
    """
    Verify that quick creation of products is disabled on the sale order
    line product fields (list product_id, list product_template_id and the
    expanded line form product_id). Other fields on the form (e.g.
    partner_id) already disable quick creation independently and must not
    be counted here.
    """

    def test_product_fields_disable_quick_create(self):
        arch = self.env["sale.order"].get_view(
            view_id=self.env.ref("sale.view_order_form").id,
            view_type="form",
        )["arch"]
        doc = etree.fromstring(arch)
        order_line = doc.xpath("//field[@name='order_line']")[0]
        # Only the editable Many2one selector widgets are creation entry
        # points; decorative fields sharing the same name (image widget,
        # bold text card) render the same product but cannot create one.
        product_fields = order_line.xpath(
            ".//field[(@name='product_id' or @name='product_template_id')"
            " and (@widget='many2one_barcode' or @widget='sol_product_many2one')]"
        )
        self.assertEqual(
            len(product_fields),
            3,
            "Expected 3 product fields (list product_id, list "
            "product_template_id and form product_id) on the order lines.",
        )
        for field in product_fields:
            options = field.get("options") or ""
            self.assertIn(
                "no_quick_create",
                options,
                f"Field {field.get('name')} (context: {etree.tostring(field)}) "
                "should disable quick creation.",
            )
