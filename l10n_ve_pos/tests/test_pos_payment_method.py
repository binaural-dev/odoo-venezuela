from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install", "pos_payment_method")
class PosPaymentMethodTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "Test Payment Method",
            "is_foreign_currency": True,
            "apply_one_cross_move": False,
        })

    def test_01_is_foreign_currency_default(self):
        pm = self.env["pos.payment.method"].create({"name": "New PM"})
        self.assertFalse(pm.is_foreign_currency)

    def test_02_is_foreign_currency_set(self):
        self.assertTrue(self.payment_method.is_foreign_currency)

    def test_03_apply_one_cross_move_default(self):
        pm = self.env["pos.payment.method"].create({"name": "New PM"})
        self.assertFalse(pm.apply_one_cross_move)
