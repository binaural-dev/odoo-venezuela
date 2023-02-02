from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("account_move","post_install", "-at_install")
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
        
    def test_foreign_rate_onchange_(self):
        with Form(self.env["account.move"]) as f:
            f.foreign_rate = 1.5
            if f.foreign_rate == 0:
                with self.assertRaises(UserError):
                    f.save()
            else:
                f.save()

    def test_get_values(self):
        self.env["account.move"].create(
            {
                "foreign_rate": 1.5,
            }
        )
        self.env["account.move"].get_values()

    def test_set_values(self):
        self.env["account.move"].create(
            {
                "foreign_rate": 1.5,
            }
        )
        self.env["account.move"].set_values()

    