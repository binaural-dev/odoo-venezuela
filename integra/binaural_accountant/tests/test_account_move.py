from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("account_move", "bin", "-at_install", "post_install")
class TestAccountMove(TransactionCase):
    def setUp(self):
        super(TestAccountMove, self).setUp()
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
        self.account = self.env["account.account"].create(
            {
                "name": "Test Account",
                "code": "TAC",
                "user_type_id": self.env.ref("account.data_account_type_revenue").id,
                "reconcile": True,
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

    # def test_01(self):
    #     """Test that the foreign currency symbol is added to the form view."""
    #     invoice_form = Form(self.env["account.move"].with_context(default_type="out_invoice"))
    #     invoice_form.partner_id = self.partner
    #     invoice_form.foreign_currency_id = self.currency
    #     invoice_form.invoice_date = "2021-01-01"
    #     with invoice_form.invoice_line_ids.new() as line_form:
    #         line_form.product_id = self.product
    #         line_form.quantity = 1
    #     invoice = invoice_form.save()
    #     self.assertEqual(invoice.foreign_currency_id.symbol, self.currency.symbol)
