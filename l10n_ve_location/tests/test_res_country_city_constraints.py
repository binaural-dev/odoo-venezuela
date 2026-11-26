from psycopg2 import IntegrityError

from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "l10n_ve_location")
class TestResCountryCityConstraints(TransactionCase):
    """Odoo 19 ignores ``_sql_constraints``: the unique (name, country, state)
    of res.country.city must be a ``models.Constraint``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.country = cls.env.ref("base.ve")
        states = cls.env["res.country.state"].search([("country_id", "=", cls.country.id)], limit=2)
        cls.state, cls.other_state = states[0], states[1]

    def _create_city(self, name="ZZ Ciudad", state=None):
        with Form(self.env["res.country.city"]) as form:
            form.country_id = self.country
            form.state_id = state or self.state
            form.name = name
        return form.save()

    def test_constraint_exists_in_database(self):
        self.env.cr.execute(
            "SELECT 1 FROM pg_constraint WHERE conrelid = 'res_country_city'::regclass "
            "AND contype = 'u' AND conname = 'res_country_city_name_uniq'"
        )
        self.assertTrue(self.env.cr.fetchone())

    def test_duplicate_city_in_same_state_is_rejected(self):
        self._create_city()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._create_city()

    def test_same_name_in_other_state_is_allowed(self):
        first = self._create_city()
        second = self._create_city(state=self.other_state)
        self.assertNotEqual(first, second)
