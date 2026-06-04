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

    def test_check_vat_invalid_characters(self):
        self.partner.vat = "12A34"
        with self.assertRaises(MissingError):
            self.partner._check_vat()

    def test_check_vat_valid(self):
        self.partner.vat = "123456"
        # Should not raise
        self.partner._check_vat()

    def test_duplicate_vat_with_active_ids_context_still_fails(self):
        partner_2 = self.env["res.partner"].create({
            "name": "Context Partner",
            "prefix_vat": "V",
            "vat": "99887766",
            "email": "context@example.com",
            "country_id": self.env.ref("base.ve").id,
        })

        with self.assertRaises(ValidationError):
            partner_2.with_context(
                active_model="res.partner",
                active_ids=[self.partner.id, partner_2.id],
            ).write({"prefix_vat": "V", "vat": self.partner.vat})

    def test_duplicate_vat_with_explicit_merge_context_is_allowed(self):
        partner_2 = self.env["res.partner"].create({
            "name": "Merge Partner",
            "prefix_vat": "V",
            "vat": "11223344",
            "email": "merge@example.com",
            "country_id": self.env.ref("base.ve").id,
        })

        partner_2.with_context(
            l10n_ve_partner_merge_validation=True,
            l10n_ve_merge_partner_ids=[self.partner.id, partner_2.id],
        ).write({"prefix_vat": "V", "vat": self.partner.vat})

        self.assertEqual(partner_2.vat, self.partner.vat)

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
