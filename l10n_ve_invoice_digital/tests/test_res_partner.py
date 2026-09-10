from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "res_partner_digital")
class TestResPartnerEmailDuplicate(TransactionCase):
    """Con l10n_ve_invoice_digital instalado, la validación de correos duplicados
    de l10n_ve_contact queda desactivada (ticket 14242).
    """

    def setUp(self):
        super().setUp()
        # Las banderas de l10n_ve_contact que habilitan la validación original:
        # se activan para que el test falle si el override desaparece.
        self.env.company.write({
            "validate_user_creation_by_company": True,
        })
        self.partner_1 = self.env["res.partner"].create({
            "name": "Partner 1",
            "email": "test_duplicate@example.com",
        })

    def test_01_duplicate_email_allowed_on_create(self):
        """Un segundo contacto puede crearse con el mismo correo del primero."""
        partner_2 = self.env["res.partner"].create({
            "name": "Partner 2",
            "email": "test_duplicate@example.com",
        })
        self.assertTrue(partner_2.id)
        self.assertEqual(partner_2.email, self.partner_1.email)

    def test_02_duplicate_email_allowed_on_write(self):
        """Un contacto existente puede actualizarse al correo de otro contacto."""
        partner_2 = self.env["res.partner"].create({
            "name": "Partner 2",
            "email": "otro_correo@example.com",
        })
        partner_2.write({"email": "test_duplicate@example.com"})
        self.assertEqual(partner_2.email, self.partner_1.email)

    def test_03_check_duplicate_email_is_noop(self):
        """La sobrescritura no valida nada y no devuelve valor."""
        self.assertIsNone(
            self.partner_1.check_duplicate_email("test_duplicate@example.com")
        )
