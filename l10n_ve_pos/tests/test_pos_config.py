from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from unittest.mock import patch


@tagged("post_install", "-at_install", "pos_config")
class PosConfigTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency_usd = cls.env["res.currency"].create({
            "name": "USD",
            "symbol": "$",
            "rounding": 0.01,
        })
        cls.company.foreign_currency_id = cls.currency_usd

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Config",
            "company_id": cls.company.id,
            "foreign_currency_id": cls.currency_usd.id,
        })

    def test_01_foreign_currency_id_related(self):
        self.assertEqual(
            self.pos_config.foreign_currency_id,
            self.company.foreign_currency_id,
        )

    def test_02_compute_rate(self):
        rate_model = self.env["res.currency.rate"]
        with patch.object(rate_model.__class__, "compute_rate") as mock_compute:
            mock_compute.return_value = {"foreign_rate": 40.0, "foreign_inverse_rate": 0.025}
            self.pos_config._compute_rate()
            self.pos_config.foreign_rate = 40.0
            self.pos_config.foreign_inverse_rate = 0.025

    def test_03_related_fields(self):
        self.assertIsInstance(self.pos_config.pos_show_free_qty, bool)
        self.assertIsInstance(self.pos_config.sell_kit_from_another_store, bool)
        self.assertIsInstance(self.pos_config.pos_show_just_products_with_available_qty, bool)
        self.assertIsInstance(self.pos_config.pos_search_cne, bool)
        self.assertIsInstance(self.pos_config.amount_to_zero, bool)
        self.assertIsInstance(self.pos_config.activate_barcode_strict_mode, bool)
        self.assertIsInstance(self.pos_config.validate_phone_in_pos, bool)

    def test_04_action_to_open_ui_validates_foreign_currency(self):
        session = self.env["pos.session"].create({
            "config_id": self.pos_config.id,
            "user_id": self.env.uid,
        })
        self.pos_config.current_session_id = session
        session.foreign_currency_id = self.currency_usd

        with patch.object(type(self.pos_config), "_action_to_open_ui") as mock:
            mock.return_value = {}
            result = self.pos_config._action_to_open_ui()
            self.assertEqual(result, {})

    def test_05_action_to_open_ui_raises_without_foreign_currency(self):
        session = self.env["pos.session"].create({
            "config_id": self.pos_config.id,
            "user_id": self.env.uid,
        })
        self.pos_config.current_session_id = session
        session.foreign_currency_id = False

        with self.assertRaises(ValidationError):
            self.pos_config._action_to_open_ui()
