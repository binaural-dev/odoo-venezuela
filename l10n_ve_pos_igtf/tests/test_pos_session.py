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
        cls.currency_vef = cls.env["res.currency"].search([("name", "=", "VEF")], limit=1)
        if cls.currency_vef:
            cls.company.currency_id = cls.currency_vef
        cls.currency_usd = cls.env.ref("base.USD")
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

    def _patch_parent(self, model_name, method_name, **kwargs):
        model_class = self.env[model_name].__class__
        for klass in model_class.__mro__[1:]:
            if method_name in klass.__dict__:
                return patch.object(klass, method_name, **kwargs)
        return patch.object(model_class.__bases__[0], method_name, **kwargs)

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
        with self._patch_parent("pos.session", "load_pos_data", return_value=data):
            result = self.pos_session.load_pos_data()
            self.assertIn("pos.payment.method", result)
            pm_data = result["pos.payment.method"][0]
            self.assertEqual(pm_data["apply_igtf"], True)

    def test_02_action_pos_session_open_success(self):
        with self._patch_parent("pos.session", "action_pos_session_open", return_value={}):
            result = self.pos_session.action_pos_session_open()
            self.assertEqual(result, {})

    def test_03_action_pos_session_open_fails_without_igtf_account(self):
        self.company.customer_account_igtf_id = False
        with self.assertRaises(ValidationError):
            self.pos_session.action_pos_session_open()

    def test_04_action_pos_session_open_succeeds_with_igtf_account(self):
        self.company.customer_account_igtf_id = self.account_igtf
        with self._patch_parent("pos.session", "action_pos_session_open", return_value={}):
            result = self.pos_session.action_pos_session_open()
            self.assertEqual(result, {})
