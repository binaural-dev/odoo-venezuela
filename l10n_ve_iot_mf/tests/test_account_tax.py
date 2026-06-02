from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestAccountTaxInherit(TransactionCase):

    def setUp(self):
        super().setUp()

    def test_fiscal_code_default_zero(self):
        """El campo fiscal_code debe tener default=0."""
        tax = self.env["account.tax"].create({
            "name": "Test Tax",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
        })
        self.assertEqual(tax.fiscal_code, 0)

    def test_fiscal_code_custom_value(self):
        """Se puede asignar un valor custom a fiscal_code."""
        tax = self.env["account.tax"].create({
            "name": "Test Tax",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "fiscal_code": 3,
        })
        self.assertEqual(tax.fiscal_code, 3)

    def test_fiscal_code_in_pos_data_fields(self):
        """_load_pos_data_fields debe incluir 'fiscal_code'."""
        tax = self.env["account.tax"].create({
            "name": "Test Tax",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "fiscal_code": 2,
        })
        fields = tax._load_pos_data_fields(False)
        self.assertIn("fiscal_code", fields)
