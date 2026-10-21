from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "res_partner_digital")
class TestResPartnerEmailDuplicate(TransactionCase):
    """En compañías que digitalizan con TFHKA, la validación de correos duplicados
    de l10n_ve_contact queda desactivada (ticket 14242). En el resto sigue viva.
    """

    def setUp(self):
        super().setUp()
        # Las banderas de l10n_ve_contact que habilitan la validación original:
        # se activan para que el test falle si el override desaparece.
        self.env.company.write({
            "validate_user_creation_by_company": True,
            "invoice_digital_tfhka": True,
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

    def test_04_validation_still_applies_without_tfhka(self):
        """En una compañía que NO digitaliza con TFHKA la validación sigue viva.

        El override es un bypass para el flujo de digitalización, no una
        desactivación global: si se vuelve incondicional, este test falla.
        """
        self.env.company.invoice_digital_tfhka = False
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create({
                "name": "Partner 3",
                "email": "test_duplicate@example.com",
            })

    def test_05_decision_uses_company_id_param_not_active_company(self):
        """La decision debe tomarse por la compañia recibida en
        ``company_id``, no por ``self.env.company`` (bug corregido).

        La compañia ACTIVA si digitaliza con TFHKA, pero el ``company_id``
        pasado explicitamente es de otra compañia que NO digitaliza: la
        validacion debe seguir aplicando para esa compañia, sin importar cual
        sea la activa. Antes, al mirar solo ``self.env.company``, un usuario
        con la compañia TFHKA activa podia colar duplicados que en realidad
        pertenecen a otra compañia.

        ``existing_partner`` debe pertenecer realmente a ``other_company``
        (``company_id``) y el chequeo debe hacerse desde un partner DISTINTO:
        el dominio de ``check_duplicate_email`` siempre excluye a ``self``
        (ver ``l10n_ve_contact``), así que validar "contra sí mismo" nunca
        encontraría nada sin importar el bug.
        """
        other_company = self.env["res.company"].create({
            "name": "Otra Compañia (no TFHKA)",
            "invoice_digital_tfhka": False,
            "validate_user_creation_by_company": True,
        })
        existing_partner = self.env["res.partner"].create({
            "name": "Partner de Otra Compania",
            "email": "otra_compania@example.com",
            "company_id": other_company.id,
        })
        checking_partner = self.env["res.partner"].create({
            "name": "Partner que valida",
            "email": "unrelated@example.com",
        })
        with self.assertRaises(ValidationError):
            checking_partner.check_duplicate_email(
                existing_partner.email, company_id=other_company.id
            )

    def test_06_decision_skips_validation_for_tfhka_company_id_param(self):
        """A la inversa: la compañia ACTIVA no digitaliza, pero el
        ``company_id`` recibido si lo hace -- la validacion debe omitirse
        para esa compañia (antes, al mirar solo ``self.env.company``,
        igual se validaba porque la activa no era TFHKA)."""
        self.env.company.invoice_digital_tfhka = False
        tfhka_company = self.env["res.company"].create({
            "name": "Compañia TFHKA",
            "invoice_digital_tfhka": True,
            "validate_user_creation_by_company": True,
        })
        self.assertIsNone(
            self.partner_1.check_duplicate_email(
                "test_duplicate@example.com", company_id=tfhka_company.id
            )
        )
