from odoo import _
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged("sale_order", "post_install", "-at_install")
class TestSaleOrder(TransactionCase):

    def setUp(self):
        super(TestSaleOrder, self).setUp()
        self.company = self.env["res.company"].create(
            {
                "name": "Test Company",
                "currency_foreign_id": self.env.ref("base.USD").id,
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
        self.env.company.currency_foreign_id = self.env.ref("base.VEF")
        sale_form = Form(self.env["sale.order"])
        sale_form.partner_id = self.partner
        sale_form.foreign_rate = 20
        with sale_form.order_line.new() as line_form:
            line_form.product_id = self.product
            line_form.product_uom_qty = 1
            line_form.price_unit = 200
            if line_form.foreign_price > 0:
                sale_form.save()

    def test_02(self):
        """Test that the foreign currency symbol is added to the form view."""
        self.env.company.currency_foreign_id = self.env.ref("base.VEF")
        sale_form = Form(self.env["sale.order"])
        sale_form.partner_id = self.partner
        sale_form.foreign_rate = 20
        with sale_form.order_line.new() as line_form:
            line_form.product_id = self.product
            line_form.product_uom_qty = 2
            line_form.price_unit = 100
            if line_form.foreign_price > 0:
                sale_form.save()
            