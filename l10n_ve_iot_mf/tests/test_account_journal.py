from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestAccountJournal(TransactionCase):

    def setUp(self):
        super().setUp()

    def test_payment_method_default_01(self):
        """El campo payment_method debe tener default='01'."""
        journal = self.env["account.journal"].create({
            "name": "Test Journal",
            "code": "TEST",
            "type": "sale",
        })
        self.assertEqual(journal.payment_method, "01")

    def test_payment_method_custom_value(self):
        """Se puede asignar un valor custom a payment_method."""
        journal = self.env["account.journal"].create({
            "name": "Test Journal",
            "code": "TEST",
            "type": "sale",
            "payment_method": "03",
        })
        self.assertEqual(journal.payment_method, "03")

    def test_payment_method_max_size_2(self):
        """payment_method debe tener size=2."""
        journal = self.env["account.journal"].create({
            "name": "Test Journal",
            "code": "TEST",
            "type": "sale",
            "payment_method": "99",
        })
        self.assertEqual(len(journal.payment_method), 2)
