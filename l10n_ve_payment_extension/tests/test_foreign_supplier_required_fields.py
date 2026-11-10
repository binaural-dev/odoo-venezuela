import itertools

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
        cls.type_person_non_resident = cls.env.ref(
            "l10n_ve_payment_extension.type_person_four_l10n_ve_payment_extension"
        )

    def _fill_form(self, supplier=True, country=None, taxpayer_type=None,
                   withholding=False, type_person=None):
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
        form.type_person_id = type_person or self.type_person
        if taxpayer_type is None:
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
        self.assertFalse(partner.taxpayer_type)
        self.assertFalse(partner.withholding_type_id)

    def test_venezuelan_ordinary_and_formal_have_no_withholding(self):
        for taxpayer_type in ("ordinary", "formal"):
            form = self._fill_form(supplier=False, taxpayer_type=taxpayer_type)
            # The field is invisible, so the form refuses to write it.
            with self.assertRaisesRegex(AssertionError, "invisible field"):
                form.withholding_type_id = self.withholding_100
            partner = form.save()
            self.assertTrue(partner.is_resident_person)
            self.assertFalse(partner.withholding_type_id)

    def test_special_customer_defaults_withholding_to_75(self):
        partner = self._fill_form(supplier=False, taxpayer_type="special").save()
        self.assertEqual(partner.withholding_type_id, self.withholding_75)

    def test_supplier_keeps_the_withholding_type_field_for_any_taxpayer_type(self):
        # Retentions of a supplier read its withholding type, so the rule of the
        # ticket does not apply: no default, no clearing, field always visible.
        for taxpayer_type in ("ordinary", "formal", "special"):
            form = self._fill_form(taxpayer_type=taxpayer_type)
            self.assertFalse(form.withholding_type_id)
            form.withholding_type_id = self.withholding_100
            form.taxpayer_type = "ordinary"
            self.assertEqual(form.withholding_type_id, self.withholding_100)
            self.assertEqual(form.save().withholding_type_id, self.withholding_100)

    def test_special_resident_can_choose_100(self):
        for supplier in (True, False):
            form = self._fill_form(supplier=supplier, taxpayer_type="special")
            form.withholding_type_id = self.withholding_100
            self.assertEqual(form.save().withholding_type_id, self.withholding_100)

    @mute_logger("odoo.tests.form")
    def test_special_customer_requires_withholding_when_cleared(self):
        form = self._fill_form(supplier=False, taxpayer_type="special")
        form.withholding_type_id = self.env["account.withholding.type"]
        with self.assertRaisesRegex(AssertionError, "withholding_type_id"):
            form.save()

    def test_special_to_ordinary_clears_the_withholding(self):
        form = self._fill_form(supplier=False, taxpayer_type="special")
        self.assertEqual(form.withholding_type_id, self.withholding_75)
        form.taxpayer_type = "ordinary"
        self.assertFalse(form.withholding_type_id)

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
        self.assertFalse(partner.taxpayer_type)

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
        self.assertFalse(partner.taxpayer_type)

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
