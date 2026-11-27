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
            "is_company": True,
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
            "is_company": True,
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

    def _create_user(self, login, with_group):
        groups = [
            self.env.ref("base.group_user").id,
            self.env.ref("base.group_partner_manager").id,
        ]
        if with_group:
            groups.append(
                self.env.ref("l10n_ve_contact.group_edit_partner_name_immutable").id
            )
        return self.env["res.users"].create({
            "name": login,
            "login": login,
            "group_ids": [(6, 0, groups)],
        })

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

        user = self._create_user("name_blocked", with_group=False)
        with self.assertRaises(ValidationError):
            self.partner.with_user(user).write({"name": "Should Fail"})

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

    def test_name_change_allowed_with_group_when_enabled(self):
        self.company.write({"validate_partner_name_immutable": True})

        created = self._create_partner_transaction(self.partner)
        if not created:
            self.skipTest(
                "No transaction model available in this test environment "
                "(sale.order/purchase.order)."
            )

        user = self._create_user("name_editor", with_group=True)
        self.partner.with_user(user).write({"name": "Renamed By Group"})
        self.assertEqual(self.partner.name, "Renamed By Group")

    def test_allowed_prefix_vat_by_contact_type(self):
        # Task 87829: a person is V, E or P; a company is J, G or C.
        person = self.env["res.partner"].new({"is_company": False})
        company = self.env["res.partner"].new({"is_company": True})
        self.assertEqual(person.allowed_prefix_vat, ["V", "E", "P"])
        self.assertEqual(company.allowed_prefix_vat, ["J", "G", "C"])

    def test_changing_contact_type_fixes_the_prefix_vat(self):
        partner = self.env["res.partner"].new({"is_company": True, "prefix_vat": "V"})
        partner._onchange_is_company_prefix_vat()
        self.assertEqual(partner.prefix_vat, "J")
        partner.is_company = False
        partner._onchange_is_company_prefix_vat()
        self.assertEqual(partner.prefix_vat, "V")

    def test_changing_contact_type_keeps_an_allowed_prefix_vat(self):
        for is_company, prefix in ((True, "G"), (True, "C"), (False, "E"), (False, "P")):
            partner = self.env["res.partner"].new(
                {"is_company": is_company, "prefix_vat": prefix}
            )
            partner._onchange_is_company_prefix_vat()
            self.assertEqual(partner.prefix_vat, prefix)

    def test_default_prefix_vat_follows_the_contact_type_of_the_action(self):
        partner_model = self.env["res.partner"]
        self.assertEqual(partner_model.default_get(["prefix_vat"])["prefix_vat"], "V")
        defaults = partner_model.with_context(default_is_company=True).default_get(
            ["prefix_vat"]
        )
        self.assertEqual(defaults["prefix_vat"], "J")

    def test_rif_prefix_must_match_the_contact_type(self):
        # Task 87829: the rule holds on save, not only in the form.
        Partner = self.env["res.partner"]
        with self.assertRaises(ValidationError):
            Partner.create(
                {"name": "Company V", "is_company": True, "prefix_vat": "V", "vat": "111111111"}
            )
        with self.assertRaises(ValidationError):
            Partner.create(
                {"name": "Person J", "is_company": False, "prefix_vat": "J", "vat": "22222222"}
            )
        with self.assertRaises(ValidationError):
            self.partner.is_company = True  # keeps V with a number
        company = Partner.create(
            {"name": "Company J", "is_company": True, "prefix_vat": "J", "vat": "333333333"}
        )
        self.assertEqual(company.prefix_vat, "J")

    def test_partner_without_number_is_not_checked(self):
        partner = self.env["res.partner"].create({"name": "No RIF", "is_company": True})
        self.assertEqual(partner.prefix_vat, "J")
        # Nor is one without prefix: there is no mismatch to report.
        partner = self.env["res.partner"].create(
            {"name": "No prefix", "is_company": True, "prefix_vat": False, "vat": "666666666"}
        )
        self.assertFalse(partner.prefix_vat)

    def test_company_partner_accepts_any_prefix(self):
        # A company can be a legal entity (J) or a sole proprietorship (V).
        partner = self.env.company.partner_id
        self.assertEqual(
            partner.allowed_prefix_vat, ["V", "E", "J", "G", "P", "C"]
        )
        partner.write({"vat": "444444444", "prefix_vat": "V"})
        partner.write({"prefix_vat": "J"})

    def test_prefix_vat_default_on_create_follows_is_company_not_the_context(self):
        # The contacts of a company are created from its form, with the context
        # of the action (default_is_company) but as persons.
        partner_model = self.env["res.partner"].with_context(default_is_company=True)
        parent = partner_model.create(
            {"name": "Parent J", "is_company": True, "prefix_vat": "J", "vat": "777777777"}
        )
        contact = partner_model.create(
            {"name": "Contact", "parent_id": parent.id, "is_company": False, "vat": "88888888"}
        )
        self.assertEqual(contact.prefix_vat, "V")
        company = partner_model.create(
            {"name": "Another company", "is_company": True, "vat": "999999999"}
        )
        self.assertEqual(company.prefix_vat, "J")
