import itertools

from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger

_counter = itertools.count(1)


@tagged("post_install", "-at_install", "foreign_supplier_required_fields")
class TestForeignSupplierRequiredFields(TransactionCase):
    """Ticket 16153: taxpayer type and withholding type are not required for
    foreign suppliers (country different from Venezuela).
    Ticket 16339: the withholding type depends on the taxpayer type, but only for
    partners that are not suppliers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country_ve = cls.env.ref("base.ve")
        cls.country_us = cls.env.ref("base.us")
        cls.state_ve = cls.env["res.country.state"].search(
            [("country_id", "=", cls.country_ve.id)], limit=1
        )
        cls.state_us = cls.env["res.country.state"].search(
            [("country_id", "=", cls.country_us.id)], limit=1
        )
        # l10n_ve_location requires city, municipality and parish in the form.
        cls.locations = {}
        for country, state in (
            (cls.country_ve, cls.state_ve),
            (cls.country_us, cls.state_us),
        ):
            city = cls.env["res.country.city"].create(
                {"name": "Test City %s" % country.code,
                 "country_id": country.id, "state_id": state.id}
            )
            municipality = cls.env["res.country.municipality"].create(
                {"name": "TEST MUNICIPALITY %s" % country.code,
                 "code": "TM%s" % country.code, "country_id": country.id,
                 "state_id": [(6, 0, state.ids)]}
            )
            parish = cls.env["res.country.parish"].create(
                {"name": "Test Parish %s" % country.code,
                 "code": "TP%s" % country.code, "municipality_id": municipality.id}
            )
            cls.locations[country.code] = (city, municipality, parish)
        cls.type_person = cls.env.ref(
            "l10n_ve_payment_extension.type_person_l10n_ve_payment_extension"
        )
        cls.withholding_75 = cls.env.ref(
            "l10n_ve_payment_extension.account_withholding_type_75"
        )
        cls.withholding_100 = cls.env.ref(
            "l10n_ve_payment_extension.account_withholding_type_100"
        )
        cls.type_person_pj = cls.env.ref(
            "l10n_ve_payment_extension.type_person_three_l10n_ve_payment_extension"
        )
        cls.type_person_non_resident = cls.env.ref(
            "l10n_ve_payment_extension.type_person_two_l10n_ve_payment_extension"
        )

    def _fill_form(self, supplier=True, country=None, taxpayer_type=None,
                   withholding=False, type_person=None, company=False):
        """Fill the fields that the installed views require, with unique data."""
        number = next(_counter)
        country = country or self.country_ve
        context = {"default_supplier_rank": 1} if supplier else {}
        form = Form(self.env["res.partner"].with_context(**context))
        form.name = "Foreign Supplier Test %s" % number
        form.prefix_vat = "J"
        form.vat = "%09d" % (700000000 + number)
        form.street = "Street %s" % number
        form.country_id = country
        state = self.state_ve if country == self.country_ve else self.state_us
        form.state_id = state
        city, municipality, parish = self.locations[country.code]
        form.city_id = city
        form.municipality = municipality
        form.parish_id = parish
        if company:
            form.company_type = "company"
            type_person = type_person or self.type_person_pj
        form.type_person_id = type_person or self.type_person
        if form.is_non_resident_person:
            # Ticket 86944: taxpayer and withholding types are invisible.
            pass
        elif taxpayer_type is None:
            # The default is 'ordinary'; clear it to test the required modifier.
            form.taxpayer_type = False
        else:
            form.taxpayer_type = taxpayer_type
        if withholding:
            form.withholding_type_id = withholding
        return form

    def test_foreign_supplier_saves_without_taxpayer_nor_withholding(self):
        form = self._fill_form(
            country=self.country_us, type_person=self.type_person_non_resident
        )
        partner = form.save()
        self.assertTrue(partner.is_foreign_partner)
        self.assertEqual(partner.taxpayer_type, "ordinary")
        self.assertFalse(partner.withholding_type_id)

    def test_pj_domiciliada_ordinary_and_formal_have_no_withholding(self):
        for taxpayer_type in ("ordinary", "formal"):
            form = self._fill_form(
                supplier=False, taxpayer_type=taxpayer_type, company=True
            )
            # The field is invisible, so the form refuses to write it.
            with self.assertRaisesRegex(AssertionError, "invisible field"):
                form.withholding_type_id = self.withholding_100
            partner = form.save()
            self.assertTrue(partner.is_resident_person)
            self.assertFalse(partner.withholding_type_id)

    def test_pj_domiciliada_special_defaults_withholding_to_75(self):
        partner = self._fill_form(
            supplier=False, taxpayer_type="special", company=True
        ).save()
        self.assertEqual(partner.withholding_type_id, self.withholding_75)

    def test_supplier_has_the_same_rule_as_any_other_partner(self):
        # The rule does not depend on supplier_rank (it is 0 in the web client).
        for supplier in (True, False):
            form = self._fill_form(
                supplier=supplier, taxpayer_type="special", company=True
            )
            self.assertEqual(form.withholding_type_id, self.withholding_75)

    def test_pj_domiciliada_special_can_choose_100(self):
        for supplier in (True, False):
            form = self._fill_form(
                supplier=supplier, taxpayer_type="special", company=True
            )
            form.withholding_type_id = self.withholding_100
            self.assertEqual(form.save().withholding_type_id, self.withholding_100)

    @mute_logger("odoo.tests.form")
    def test_pj_domiciliada_special_requires_withholding_when_cleared(self):
        form = self._fill_form(supplier=False, taxpayer_type="special", company=True)
        form.withholding_type_id = self.env["account.withholding.type"]
        with self.assertRaisesRegex(AssertionError, "withholding_type_id"):
            form.save()

    def test_pj_domiciliada_special_to_ordinary_clears_the_withholding(self):
        form = self._fill_form(supplier=False, taxpayer_type="special", company=True)
        self.assertEqual(form.withholding_type_id, self.withholding_75)
        form.taxpayer_type = "ordinary"
        self.assertFalse(form.withholding_type_id)

    def test_pn_residente_ordinary_and_formal_default_to_100_and_require_it(self):
        for taxpayer_type in ("ordinary", "formal"):
            form = self._fill_form(supplier=False, taxpayer_type=taxpayer_type)
            self.assertEqual(form.withholding_type_id, self.withholding_100)
            self.assertEqual(form.save().withholding_type_id, self.withholding_100)
        form = self._fill_form(supplier=False, taxpayer_type="ordinary")
        form.withholding_type_id = self.env["account.withholding.type"]
        with self.assertRaisesRegex(AssertionError, "withholding_type_id"):
            form.save()

    def test_pn_residente_special_has_no_withholding(self):
        # Sheet "Matriz de retenciones", row 18: N/A and not required.
        form = self._fill_form(supplier=False, taxpayer_type="ordinary")
        self.assertEqual(form.withholding_type_id, self.withholding_100)
        form.taxpayer_type = "special"
        self.assertFalse(form.withholding_type_id)
        with self.assertRaisesRegex(AssertionError, "invisible field"):
            form.withholding_type_id = self.withholding_75
        self.assertFalse(form.save().withholding_type_id)
        form = self._fill_form(supplier=False, taxpayer_type="special")
        form.taxpayer_type = "formal"
        self.assertEqual(form.withholding_type_id, self.withholding_100)

    def test_resident_person_types(self):
        ref = self.env.ref
        for name, expected in (
            ("type_person_l10n_ve_payment_extension", True),
            ("type_person_two_l10n_ve_payment_extension", False),
            ("type_person_three_l10n_ve_payment_extension", True),
            ("type_person_four_l10n_ve_payment_extension", False),
            ("type_person_five_l10n_ve_payment_extension", False),
            ("type_person_six_l10n_ve_payment_extension", False),
            ("type_person_seven_l10n_ve_payment_extension", True),
        ):
            partner = self.env["res.partner"].new(
                {"name": name, "type_person_id": ref(f"l10n_ve_payment_extension.{name}").id}
            )
            self.assertEqual(partner.is_resident_person, expected, name)

    def test_foreign_customer_saves_without_taxpayer_type(self):
        partner = self._fill_form(
            supplier=False,
            country=self.country_us,
            type_person=self.type_person_non_resident,
        ).save()
        self.assertTrue(partner.is_foreign_partner)
        self.assertEqual(partner.taxpayer_type, "ordinary")

    @mute_logger("odoo.tests.form")
    def test_resident_person_type_requires_taxpayer_type_even_with_foreign_country(self):
        # The Venezuelan person types decide, whatever the country.
        form = self._fill_form(country=self.country_us)
        with self.assertRaisesRegex(AssertionError, "taxpayer_type"):
            form.save()

    def test_non_resident_person_type_is_foreign_even_with_venezuelan_country(self):
        partner = self._fill_form(
            country=self.country_ve, type_person=self.type_person_non_resident
        ).save()
        self.assertTrue(partner.is_foreign_partner)
        self.assertEqual(partner.taxpayer_type, "ordinary")

    @mute_logger("odoo.tests.form")
    def test_venezuelan_customer_requires_taxpayer_type(self):
        form = self._fill_form(supplier=False, taxpayer_type="ordinary")
        form.taxpayer_type = False
        with self.assertRaisesRegex(AssertionError, "taxpayer_type"):
            form.save()

    @mute_logger("odoo.tests.form")
    def test_supplier_without_country_still_requires_taxpayer_type(self):
        form = self._fill_form(taxpayer_type="ordinary")
        form.country_id = self.env["res.country"]
        form.taxpayer_type = False
        with self.assertRaisesRegex(AssertionError, "taxpayer_type"):
            form.save()

    def test_is_foreign_partner_method(self):
        partner_model = self.env["res.partner"]
        us_supplier = partner_model.create(
            {"name": "US supplier", "country_id": self.country_us.id,
             "supplier_rank": 1}
        )
        ve_supplier = partner_model.create(
            {"name": "VE supplier", "country_id": self.country_ve.id,
             "supplier_rank": 1}
        )
        us_customer = partner_model.create(
            {"name": "US customer", "country_id": self.country_us.id}
        )
        no_country = partner_model.create({"name": "No country", "supplier_rank": 1})
        self.assertTrue(us_supplier._is_foreign_partner())
        self.assertFalse(ve_supplier._is_foreign_partner())
        # Customers and any other contact count as foreign too.
        self.assertTrue(us_customer._is_foreign_partner())
        self.assertFalse(no_country._is_foreign_partner())

    def test_company_partner_is_never_foreign_partner(self):
        partner = self.env.company.partner_id
        partner.country_id = self.country_us
        self.assertFalse(partner._is_foreign_partner())

    def test_allowed_type_persons_by_contact_type(self):
        ref = self.env.ref
        ext = "l10n_ve_payment_extension."
        person = self.env["res.partner"].new({"name": "P", "is_company": False})
        company = self.env["res.partner"].new({"name": "C", "is_company": True})
        self.assertEqual(
            person.allowed_type_person_ids._origin.ids,
            (ref(ext + "type_person_l10n_ve_payment_extension")
             | ref(ext + "type_person_two_l10n_ve_payment_extension")).ids,
        )
        self.assertEqual(
            company.allowed_type_person_ids._origin.ids,
            (ref(ext + "type_person_three_l10n_ve_payment_extension")
             | ref(ext + "type_person_four_l10n_ve_payment_extension")
             | ref(ext + "type_person_five_l10n_ve_payment_extension")
             | ref(ext + "type_person_six_l10n_ve_payment_extension")
             | ref(ext + "type_person_seven_l10n_ve_payment_extension")).ids,
        )

    def test_changing_to_company_clears_a_person_type(self):
        form = self._fill_form(supplier=False, taxpayer_type="ordinary")
        self.assertEqual(form.type_person_id, self.type_person)
        form.company_type = "company"
        self.assertFalse(form.type_person_id)

    def test_non_resident_hides_and_clears_taxpayer_and_withholding(self):
        form = self._fill_form(supplier=False, taxpayer_type="special", company=True)
        self.assertEqual(form.withholding_type_id, self.withholding_75)
        form.type_person_id = self.type_person_non_resident
        self.assertEqual(form.taxpayer_type, "ordinary")
        self.assertFalse(form.withholding_type_id)
        with self.assertRaisesRegex(AssertionError, "invisible field"):
            form.taxpayer_type = "special"
        with self.assertRaisesRegex(AssertionError, "invisible field"):
            form.withholding_type_id = self.withholding_75

    def test_non_resident_cannot_be_special(self):
        partner = self.env["res.partner"].create(
            {"name": "NR", "type_person_id": self.type_person_non_resident.id}
        )
        with self.assertRaises(ValidationError):
            partner.taxpayer_type = "special"

    def test_pn_residente_cannot_choose_special_taxpayer(self):
        ext = "l10n_ve_payment_extension."
        for xmlid, expected in (
            ("type_person_l10n_ve_payment_extension", ["ordinary", "formal"]),
            ("type_person_three_l10n_ve_payment_extension",
             ["ordinary", "formal", "special"]),
        ):
            partner = self.env["res.partner"].new(
                {"name": "T", "type_person_id": self.env.ref(ext + xmlid).id}
            )
            self.assertEqual(partner.allowed_taxpayer_types, expected, xmlid)

    def test_choosing_pn_residente_resets_special_taxpayer(self):
        form = self._fill_form(
            supplier=False, taxpayer_type="special", company=True
        )
        self.assertEqual(form.taxpayer_type, "special")
        form.company_type = "person"
        form.type_person_id = self.type_person
        self.assertEqual(form.taxpayer_type, "ordinary")
        self.assertEqual(form.withholding_type_id, self.withholding_100)
