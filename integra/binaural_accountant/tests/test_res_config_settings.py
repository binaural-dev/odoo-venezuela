from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("res_config_settings","bin", "-at_install", "post_install")
class TestResConfigSettings(TransactionCase):
    def setUp(self):
        super(TestResConfigSettings, self).setUp()
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

    def test_currency_foreign_id_onchange_(self):
        with Form(self.env["res.config.settings"]) as f:
            f.currency_foreign_id = self.currency
            if f.currency_id == f.currency_foreign_id:
                with self.assertRaises(UserError):
                    f.save()

    def test_get_values(self):
        self.env["res.config.settings"].create(
            {
                "currency_foreign_id": self.currency.id,
            }
        )
        self.env["res.config.settings"].get_values()

    def test_set_values(self):
        self.env["res.config.settings"].create(
            {
                "currency_foreign_id": self.currency.id,
            }
        )
        self.env["res.config.settings"].set_values()
