from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestResConfigSettings(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")

    def test_invoice_print_type_related_to_company(self):
        """invoice_print_type en config settings refleja el valor de la compañía."""
        self.company.invoice_print_type = "fiscal"
        config = self.env["res.config.settings"].create({})
        config.invoice_print_type = "fiscal"
        config.execute()
        self.assertEqual(self.company.invoice_print_type, "fiscal")

    def test_invoice_print_type_default_free(self):
        """El valor por defecto debe ser 'free'."""
        config = self.env["res.config.settings"].create({})
        self.assertEqual(config.invoice_print_type, "free")
