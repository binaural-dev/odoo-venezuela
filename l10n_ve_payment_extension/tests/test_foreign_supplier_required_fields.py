import itertools

from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger

_counter = itertools.count(1)


@tagged("post_install", "-at_install", "foreign_supplier_required_fields")
class TestForeignSupplierRequiredFields(TransactionCase):
    """Ticket 16153: taxpayer type and withholding type are not required for
    foreign suppliers (country different from Venezuela)."""

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
        cls.withholding_type = cls.env["account.withholding.type"].search(
            [("state", "=", True)], limit=1
        )

    def _fill_form(self, supplier=True, country=None, taxpayer_type=None,
                   withholding=False):
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
        form.type_person_id = self.type_person
        if taxpayer_type is None:
            # The default is 'ordinary'; clear it to test the required modifier.
            form.taxpayer_type = False
        else:
            form.taxpayer_type = taxpayer_type
        if withholding:
            form.withholding_type_id = self.withholding_type
        return form

    def test_foreign_supplier_saves_without_taxpayer_nor_withholding(self):
        form = self._fill_form(country=self.country_us)
        partner = form.save()
        self.assertTrue(partner.is_foreign_supplier)
        self.assertFalse(partner.taxpayer_type)
        self.assertFalse(partner.withholding_type_id)

    @mute_logger("odoo.tests.form")
    def test_venezuelan_supplier_requires_withholding(self):
        form = self._fill_form(taxpayer_type="ordinary")
        with self.assertRaisesRegex(AssertionError, "withholding_type_id"):
            form.save()

    def test_venezuelan_supplier_with_withholding_saves(self):
        form = self._fill_form(taxpayer_type="ordinary", withholding=True)
        partner = form.save()
        self.assertFalse(partner.is_foreign_supplier)
        self.assertEqual(partner.withholding_type_id, self.withholding_type)

    @mute_logger("odoo.tests.form")
    def test_foreign_customer_still_requires_taxpayer_type(self):
        form = self._fill_form(supplier=False, country=self.country_us)
        with self.assertRaisesRegex(AssertionError, "taxpayer_type"):
            form.save()

    @mute_logger("odoo.tests.form")
    def test_supplier_without_country_still_requires_taxpayer_type(self):
        # With the withholding filled, taxpayer_type is the only missing field.
        form = self._fill_form(taxpayer_type="ordinary", withholding=True)
        form.country_id = self.env["res.country"]
        form.taxpayer_type = False
        with self.assertRaisesRegex(AssertionError, "taxpayer_type"):
            form.save()

    def test_is_foreign_supplier_method(self):
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
        self.assertTrue(us_supplier._is_foreign_supplier())
        self.assertFalse(ve_supplier._is_foreign_supplier())
        self.assertFalse(us_customer._is_foreign_supplier())
        self.assertFalse(no_country._is_foreign_supplier())

    def test_company_partner_is_never_foreign_supplier(self):
        partner = self.env.company.partner_id
        partner.supplier_rank = 1
        partner.country_id = self.country_us
        self.assertFalse(partner._is_foreign_supplier())
