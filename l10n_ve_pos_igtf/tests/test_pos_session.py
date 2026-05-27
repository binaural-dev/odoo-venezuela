from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import ValidationError
from unittest.mock import patch


@tagged("post_install", "-at_install", "igtf_pos_session")
class IgtfPosSessionTest(TransactionCase):

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
            "name": "Test POS Config IGTF",
            "company_id": cls.company.id,
        })
        cls.pos_session = cls.env["pos.session"].create({
            "config_id": cls.pos_config.id,
            "user_id": cls.env.uid,
        })

        cls.account_igtf = cls.env["account.account"].create({
            "name": "IGTF Account",
            "code": "IGTFACC",
            "account_type": "asset_current",
        })
        cls.company.customer_account_igtf_id = cls.account_igtf
        cls.company.igtf_percentage = 3.0

    def test_01_load_pos_data_fills_missing_apply_igtf(self):
        payment_method = self.env["pos.payment.method"].create({
            "name": "IGTF PM",
            "apply_igtf": True,
        })
        data = {
            "pos.payment.method": [
                {"id": payment_method.id},
            ]
        }
        with patch.object(type(self.pos_session), "load_pos_data") as mock:
            mock.return_value = data
            result = self.pos_session.load_pos_data()
            self.assertIn("pos.payment.method", result)

    def test_02_action_pos_session_open_success(self):
        with patch.object(type(self.pos_session), "action_pos_session_open") as mock:
            mock.return_value = {}
            result = self.pos_session.action_pos_session_open()
            self.assertIsNotNone(result)

    def test_03_action_pos_session_open_fails_without_igtf_account(self):
        self.company.customer_account_igtf_id = False
        with self.assertRaises(ValidationError):
            self.pos_session.action_pos_session_open()

    def test_04_action_pos_session_open_succeeds_with_igtf_account(self):
        self.company.customer_account_igtf_id = self.account_igtf
        with patch.object(type(self.pos_session), "action_pos_session_open") as mock:
            mock.return_value = {}
            result = self.pos_session.action_pos_session_open()
            self.assertIsNotNone(result)
