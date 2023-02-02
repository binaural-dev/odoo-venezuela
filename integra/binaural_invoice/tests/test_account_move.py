from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("account_move", "post_install", "-at_install")
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

    def test_create_move_line(self):
        self.env["account.move"].create(
            {
                "name": "Test Move",
                "company_id": self.company.id,
                "currency_id": self.currency.id,
                "foreign_rate": 1.5,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test Line",
                            "account_id": self.account.id,
                            "partner_id": self.partner.id,
                            "debit": 100.0,
                            "credit": 0.0,
                            "amount_currency": 150.0,
                        },
                    )
                ],
            }
        )

    
