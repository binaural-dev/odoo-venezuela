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

    def test_write_multi_record_only_changed_fails(self):
        """(p1 | p2).write({'email': x}): p1 already has x, so only p2 is
        checked; the write must fail because p2 changes to an email another
        contact owns, not because p1 rewrites its own email."""
        owner = self.env["res.partner"].create({
            "name": "Email Owner Multi",
            "prefix_vat": "J",
            "vat": "900000007",
            "email": "multi.owner@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        p1 = self.env["res.partner"].create({
            "name": "P1",
            "prefix_vat": "J",
            "vat": "900000008",
            "email": "p1@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        p2 = self.env["res.partner"].create({
            "name": "P2",
            "prefix_vat": "J",
            "vat": "900000009",
            "email": "p2@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        # p1 already shares the target email with owner (pre-existing data).
        self.env.cr.execute(
            "UPDATE res_partner SET email = %s WHERE id = %s",
            (owner.email, p1.id),
        )
        p1.invalidate_recordset(["email"])
        # Rewriting the same email on p1 alone must not raise.
        p1.write({"email": owner.email})
        # The recordset write must fail: p2 really changes to a duplicated email.
        with self.assertRaises(ValidationError):
            (p1 | p2).write({"email": owner.email})

    def test_write_unchanged_email_with_child_of_any_type(self):
        """Re-editing a contact (writing back the same email) while it has
        child addresses of any type (delivery, invoice, other) must not
        raise ValidationError."""
        for child_type in ("delivery", "invoice", "other"):
            child = self.env["res.partner"].create({
                "name": "Child %s" % child_type,
                "parent_id": self.partner.id,
                "type": child_type,
                "email": self.partner.email,
                "country_id": self.env.ref("base.ve").id,
            })
            self.assertEqual(child.type, child_type)
        self.partner.write({"email": self.partner.email, "city": "Caracas"})
        self.assertEqual(self.partner.city, "Caracas")
        self.assertEqual(self.partner.email, "test@example.com")

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

    def test_portal_address_reedit_unchanged_email(self):
        """TA 84146: portal address re-edit.

        First save creates a child address sharing the parent's email.
        Re-editing the address (e.g. changing the city) writes the partner
        with the same email: must not raise ValidationError. A really
        changed email that duplicates another partner still must.
        """
        self.env["res.partner"].create({
            "name": "Portal Delivery Address",
            "parent_id": self.partner.id,
            "type": "delivery",
            "email": self.partner.email,
            "country_id": self.env.ref("base.ve").id,
        })
        self.partner.write({"email": self.partner.email, "city": "Caracas"})
        self.assertEqual(self.partner.city, "Caracas")
        self.assertEqual(self.partner.email, "test@example.com")
        other = self.env["res.partner"].create({
            "name": "Other Portal Owner",
            "prefix_vat": "J",
            "vat": "900000005",
            "email": "other.portal@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        with self.assertRaises(ValidationError):
            self.partner.write({"email": other.email, "city": "Maracaibo"})

    def test_write_changed_email_on_delivery_address_skips_check(self):
        """Only type 'contact' is checked on write: a delivery address may
        take an email already used by another partner."""
        child = self.env["res.partner"].create({
            "name": "Portal Delivery Address 2",
            "parent_id": self.partner.id,
            "type": "delivery",
            "email": "delivery1@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        other = self.env["res.partner"].create({
            "name": "Email Owner",
            "prefix_vat": "J",
            "vat": "900000006",
            "email": "owned@example.com",
            "country_id": self.env.ref("base.ve").id,
        })
        child.write({"email": other.email})
        self.assertEqual(child.email, other.email)

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
