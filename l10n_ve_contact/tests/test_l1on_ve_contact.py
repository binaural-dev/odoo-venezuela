from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, MissingError


@tagged("res_partner", "bin", "-at_install", "post_install")
class TestResPartner(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.company.write({
            "validate_user_creation_by_company": True,
        })
        self.partner = self.env["res.partner"].create({
            "name": "Test Partner",
            "prefix_vat": "V",
            "vat": "27436422",
            "email": "test@example.com",
            "country_id": self.env.ref("base.ve").id,
        })

        self.partner_company = self.env["res.partner"].create({
            "name": "Empresa Principal, C.A.",
            "is_company": True,
            "prefix_vat": "J",
            "vat": "312345678",
            "email": "contacto@empresatest.com",
            "country_id": self.env.ref("base.ve").id,
        })

    def test_duplicate_vat(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create({
                "name": "Another",
                "prefix_vat": "V",
                "vat": "27436422",
                "email": "other@example.com",
                "country_id": self.env.ref("base.ve").id,
            })

    def test_duplicate_email_unrelated_partners(self):
        """Validar que dos contactos independientes NO puedan tener el mismo correo"""
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create({
                "name": "Cliente Ajeno",
                "prefix_vat": "V",
                "vat": "12345678",
                "email": "contacto@empresatest.com",
                "country_id": self.env.ref("base.ve").id,
            })

    def test_child_contact_same_email_on_create(self):
        """Validar que un contacto HIJO SÍ se pueda CREAR con el mismo correo de su padre"""
        child_partner = self.env["res.partner"].create({
            "name": "María Pérez (Contacto Hijo)",
            "is_company": False,
            "parent_id": self.partner_company.id,
            "email": "contacto@empresatest.com",  # Mismo correo de la casa matriz
            "country_id": self.env.ref("base.ve").id,
        })
        self.assertEqual(child_partner.email, self.partner_company.email)

    def test_child_contact_same_email_on_write(self):
        """Validar que a un contacto existente se le pueda asignar el correo de su padre mediante WRITE"""
        child_partner = self.env["res.partner"].create({
            "name": "Juan Blonco",
            "is_company": False,
            "parent_id": self.partner_company.id,
            "email": "juan@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        
        child_partner.write({
            "email": "contacto@empresatest.com"
        })
        self.assertEqual(child_partner.email, self.partner_company.email)

    def test_write_parent_id_and_email_simultaneously(self):
        """Validar que si asociamos un padre y cambiamos el email en el mismo WRITE, no falle"""
        independent_partner = self.env["res.partner"].create({
            "name": "Socio Externo",
            "email": "externo@example.com",
        })

        independent_partner.write({
            "parent_id": self.partner_company.id,
            "email": "contacto@empresatest.com",
        })
        self.assertEqual(independent_partner.parent_id.id, self.partner_company.id)

    def test_write_only_email_no_parent(self):
        """Validar que actualizar únicamente el email de un contacto sin padre 
        no cause errores (no pete) con la lógica del record.parent_id.id"""
        
        independent_partner = self.env["res.partner"].create({
            "name": "Persona Natural",
            "email": "correo.inicial@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        
        independent_partner.write({
            "email": "correo.nuevo.limpio@example.com"
        })
        
        self.assertEqual(independent_partner.email, "correo.nuevo.limpio@example.com")

    def test_check_vat_invalid_characters(self):
        self.partner.vat = "12A34"
        with self.assertRaises(MissingError):
            self.partner._check_vat()

    def test_check_vat_valid(self):
        self.partner.vat = "123456"
        # Should not raise
        self.partner._check_vat()

    def _create_partner_transaction(self, partner):
        """Create at least one related transaction for the partner when possible.

        The name immutability constraint checks different models depending on what is
        installed in the database. This helper tries the safest options and returns
        True when a record was created.
        """
        if "sale.order" in self.env.registry.models:
            self.env["sale.order"].create({"partner_id": partner.id})
            return True

        if "purchase.order" in self.env.registry.models:
            self.env["purchase.order"].create({"partner_id": partner.id})
            return True

        return False

    def test_name_change_allowed_without_transactions(self):
        self.company.write({"validate_partner_name_immutable": True})

        self.partner.write({"name": "Renamed Partner"})
        self.assertEqual(self.partner.name, "Renamed Partner")

    def test_name_change_blocked_with_transactions_when_enabled(self):
        self.company.write({"validate_partner_name_immutable": True})

        created = self._create_partner_transaction(self.partner)
        if not created:
            self.skipTest(
                "No transaction model available in this test environment "
                "(sale.order/purchase.order)."
            )

        with self.assertRaises(ValidationError):
            self.partner.write({"name": "Should Fail"})

    def test_name_change_allowed_with_transactions_when_disabled(self):
        created = self._create_partner_transaction(self.partner)
        if not created:
            self.skipTest(
                "No transaction model available in this test environment "
                "(sale.order/purchase.order)."
            )

        self.company.write({"validate_partner_name_immutable": False})
        self.partner.write({"name": "Allowed Rename"})

        self.assertEqual(self.partner.name, "Allowed Rename")
