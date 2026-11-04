from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


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

    # ------------------------------------------------------------------
    # Seguridad: ir.model.access.csv - base.group_user solo lectura,
    # CRUD completo reservado al grupo admin de TFHKA.
    # ------------------------------------------------------------------

    def test_05_plain_user_can_read_but_not_write(self):
        user = self.env["res.users"].create({
            "name": "Usuario Interno",
            "login": "plain_user_payment_method_tfhka",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        # Lectura: permitida.
        self.method.with_user(user).read(["code"])
        # Escritura, creacion y borrado: denegadas.
        with self.assertRaises(AccessError):
            self.method.with_user(user).write({"description": "Otro"})
        with self.assertRaises(AccessError):
            self.env["payment.method.tfhka"].with_user(user).create({
                "code": "QQ",
                "description": "No deberia poder",
            })
        with self.assertRaises(AccessError):
            self.method.with_user(user).unlink()

    def test_06_tfhka_admin_has_full_crud(self):
        admin_group = self.env.ref("l10n_ve_invoice_digital.group_l10n_ve_invoice_digital_admin")
        admin_user = self.env["res.users"].create({
            "name": "TFHKA Admin Payment Method",
            "login": "tfhka_admin_payment_method",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id, admin_group.id])],
        })
        created = self.env["payment.method.tfhka"].with_user(admin_user).create({
            "code": "WW",
            "description": "Transferencia",
        })
        created.with_user(admin_user).write({"description": "Transferencia bancaria"})
        self.assertEqual(created.description, "Transferencia bancaria")
        created.with_user(admin_user).unlink()
