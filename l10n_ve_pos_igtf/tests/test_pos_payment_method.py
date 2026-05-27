from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "igtf_pos_payment_method")
class IgtfPosPaymentMethodTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "Test IGTF PM",
            "apply_igtf": True,
        })

    def test_01_apply_igtf_default_false(self):
        pm = self.env["pos.payment.method"].create({"name": "New PM"})
        self.assertFalse(pm.apply_igtf)

    def test_02_apply_igtf_set_true(self):
        self.assertTrue(self.payment_method.apply_igtf)

    def test_03_load_pos_data_fields_includes_apply_igtf(self):
        config = self.env["pos.config"].create({
            "name": "Test Config",
            "company_id": self.env.company.id,
        })
        fields = self.env["pos.payment.method"]._load_pos_data_fields(config.id)
        self.assertIn("apply_igtf", fields)
