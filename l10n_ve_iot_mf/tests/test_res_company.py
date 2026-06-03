from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestResCompany(TransactionCase):

    def setUp(self):
        super().setUp()

    def test_invoice_print_type_default_free(self):
        """La compañía principal debe tener invoice_print_type='free' por defecto."""
        company = self.env.ref("base.main_company")
        self.assertEqual(company.invoice_print_type, "free")

    def test_invoice_print_type_fiscal(self):
        """Se puede cambiar invoice_print_type a 'fiscal'."""
        company = self.env.ref("base.main_company")
        company.write({"invoice_print_type": "fiscal"})
        self.assertEqual(company.invoice_print_type, "fiscal")

    def test_invoice_print_type_free(self):
        """Se puede cambiar invoice_print_type a 'free'."""
        company = self.env.ref("base.main_company")
        company.write({"invoice_print_type": "free"})
        self.assertEqual(company.invoice_print_type, "free")

    def test_invoice_print_type_invalid_value_raises(self):
        """Valores inválidos deben levantar excepción."""
        company = self.env.ref("base.main_company")
        with self.assertRaises(Exception):
            company.write({"invoice_print_type": "invalid"})
