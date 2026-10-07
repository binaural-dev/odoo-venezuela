from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "payment_method_tfhka")
class TestPaymentMethodTfhka(TransactionCase):
    def setUp(self):
        super().setUp()
        # Buscar un código de 2 caracteres que no exista
        existing = self.env["payment.method.tfhka"].search([]).mapped("code")
        import random, string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=2))
            if code not in existing:
                break
        self.code = code
        self.method = self.env["payment.method.tfhka"].create({
            "code": self.code,
            "description": "Efectivo",
        })

    def test_01_create_payment_method(self):
        self.assertTrue(self.method.id)
        self.assertEqual(self.method.code, self.code)

    def test_02_duplicate_code_raises(self):
        with self.assertRaises(ValidationError):
            self.env["payment.method.tfhka"].create({
                "code": self.code,
                "description": "Duplicado",
            })

    def test_03_unique_code_after_edit(self):
        # Generar otro código de 2 chars distinto
        other_code = "ZZ"
        other = self.env["payment.method.tfhka"].create({
            "code": other_code,
            "description": "Transferencia",
        })
        with self.assertRaises(ValidationError):
            other.code = self.code

    def test_04_search_by_name(self):
        result = self.env["payment.method.tfhka"].name_search(self.code)
        self.assertTrue(any(r[0] == self.method.id for r in result))
