from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "l10n_ve_location")
class TestCityAccess(TransactionCase):
    """
    The cities are the ones of Odoo (res.city). The core only lets the contact administrators
    manage them; the localization keeps what 19 allowed: every internal user manages the cities,
    because the contact form asks for one. Users outside the company (portal) cannot.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = new_test_user(cls.env, login="l10n_ve_city_internal", groups="base.group_user")
        cls.portal_user = new_test_user(cls.env, login="l10n_ve_city_portal", groups="base.group_portal")
        cls.state = cls.env.ref("l10n_ve_location.res_country_state_1")
        cls.city_values = {
            "name": "Ciudad de prueba",
            "country_id": cls.env.ref("base.ve").id,
            "state_id": cls.state.id,
        }

    def test_internal_user_manages_the_cities(self):
        City = self.env["res.city"].with_user(self.internal_user)
        city = City.create(self.city_values)
        city.write({"name": "Ciudad renombrada"})
        self.assertEqual(city.name, "Ciudad renombrada")
        city.unlink()
        self.assertFalse(city.exists())

    def test_portal_user_cannot_manage_the_cities(self):
        City = self.env["res.city"].with_user(self.portal_user)
        with self.assertRaises(AccessError):
            City.create(self.city_values)
        city = self.env["res.city"].create(self.city_values)
        with self.assertRaises(AccessError):
            city.with_user(self.portal_user).write({"name": "Ciudad renombrada"})
        with self.assertRaises(AccessError):
            city.with_user(self.portal_user).unlink()
