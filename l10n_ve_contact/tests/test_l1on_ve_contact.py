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

    def test_duplicate_vat(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create({
                "name": "Another",
                "prefix_vat": "V",
                "vat": "27436422",
                "email": "other@example.com",
                "country_id": self.env.ref("base.ve").id,
            })

    def test_duplicate_email(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create({
                "name": "Other",
                "prefix_vat": "V",
                "vat": "12345678",
                "email": "test@example.com",
                "country_id": self.env.ref("base.ve").id,
            })

    def test_duplicate_email_in_same_batch(self):
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create([
                {
                    "name": "Batch A",
                    "prefix_vat": "J",
                    "vat": "900000001",
                    "email": "batch@example.com",
                    "country_id": self.env.ref("base.ve").id,
                },
                {
                    "name": "Batch B",
                    "prefix_vat": "J",
                    "vat": "900000002",
                    "email": "batch@example.com",
                    "country_id": self.env.ref("base.ve").id,
                },
            ])

    def test_write_same_email_on_already_duplicated_partners(self):
        other = self.env["res.partner"].create({
            "name": "Shares email",
            "prefix_vat": "J",
            "vat": "900000003",
            "email": "shared@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        # Data that already came duplicated (e.g. an old import).
        self.env.cr.execute(
            "UPDATE res_partner SET email = %s WHERE id = %s",
            ("shared@example.com", self.partner.id),
        )
        self.partner.invalidate_recordset(["email"])
        self.partner.write({"email": "shared@example.com", "phone": "02125550000"})
        self.assertEqual(self.partner.email, other.email)

    def test_write_new_duplicated_email(self):
        self.env["res.partner"].create({
            "name": "Owner",
            "prefix_vat": "J",
            "vat": "900000004",
            "email": "owner@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        with self.assertRaises(ValidationError):
            self.partner.write({"email": "owner@example.com"})

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
