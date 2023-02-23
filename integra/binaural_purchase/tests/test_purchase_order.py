from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("purchase_order", "bin", "-at_install")
class TestPurchaseOrder(TransactionCase):

    def setUp(self):
        super(TestPurchaseOrder, self).setUp()
        self.company = self.env["res.company"].create(
            {
                "name": "Test Company",
                "currency_id": self.env.ref("base.USD").id,
            }
        )
        self.currency = self.env["res.currency"].create(
            {
                "name": "Test Currency",
                "symbol": "TC",
                "rounding": 0.01,
                "position": "after",
                "active": True,
            }
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "email": "",
                "vat": "27436422",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "service",
                "list_price": 100,
                "taxes_id": False,
            }
        )

    def test_01(self):
        """Test that the foreign currency symbol is added to the form view."""
        purchase_form = Form(self.env["purchase.order"])
        purchase_form.partner_id = self.partner
        purchase_form.date_order = "2021-01-01"
        with purchase_form.order_line.new() as line_form:
            line_form.product_id = self.product
            line_form.product_qty = 1
        purchase_form.save()

    def test_02(self):
        """Test that the foreign currency symbol is added to the form view."""
        purchase_form = Form(self.env["purchase.order"])
        purchase_form.partner_id = self.partner
        purchase_form.date_order = "2021-01-01"
        with purchase_form.order_line.new() as line_form:
            line_form.product_id = self.product
            line_form.product_qty = 1
        purchase_form.save()
