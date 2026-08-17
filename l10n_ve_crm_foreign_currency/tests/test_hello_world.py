from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_crm_foreign_currency")
class TestHelloWorld(TransactionCase):
    def test_hello_world(self):
        self.assertTrue(True)
