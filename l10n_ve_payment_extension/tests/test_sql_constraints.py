from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "l10n_ve_payment_extension")
class TestSqlConstraints(TransactionCase):
    """Odoo 19 ignores ``_sql_constraints``: UNIQUE and CHECK of the retention
    configuration models must be ``models.Constraint``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        country = cls.env.ref("base.ve")
        cls.municipality = cls.env["res.country.municipality"].create(
            {
                "name": "ZZ Municipio",
                "code": "ZZM1",
                "country_id": country.id,
                "state_id": [(6, 0, cls.env["res.country.state"].search(
                    [("country_id", "=", country.id)], limit=1).ids)],
            }
        )
        cls.other_municipality = cls.municipality.copy({"name": "ZZ Municipio 2", "code": "ZZM2"})
        cls.branch = cls.env["economic.branch"].create({"name": "ZZ RAMA BASE"})

    def _db_constraint(self, table, name):
        self.env.cr.execute(
            "SELECT 1 FROM pg_constraint WHERE conrelid = %s::regclass AND conname = %s",
            (table, name),
        )
        return bool(self.env.cr.fetchone())

    def test_constraints_exist_in_database(self):
        for table, name in (
            ("account_withholding_type", "account_withholding_type_unique_name"),
            ("account_withholding_type", "account_withholding_type_unique_value"),
            ("economic_activity", "economic_activity_code_uniq"),
            ("economic_activity", "economic_activity_aliquot_mayor_cero"),
            ("economic_branch", "economic_branch_name_uniq"),
            ("payment_concept_line", "payment_concept_line_unique_code"),
        ):
            self.assertTrue(self._db_constraint(table, name), f"{name} missing")

    # --- account.withholding.type -------------------------------------
    def _withholding(self, name, value):
        with Form(self.env["account.withholding.type"]) as form:
            form.name = name
            form.value = value
        return form.save()

    def test_withholding_type_duplicate_name_is_rejected(self):
        self._withholding("ZZ RET", 71.0)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._withholding("ZZ RET", 72.0)

    def test_withholding_type_duplicate_value_is_rejected(self):
        self._withholding("ZZ RET A", 73.0)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._withholding("ZZ RET B", 73.0)

    # --- economic.branch ----------------------------------------------
    def test_economic_branch_duplicate_name_is_rejected(self):
        # A Python validation raises first; the UNIQUE is the safety net.
        with self.assertRaises(Exception) as caught, mute_logger("odoo.sql_db"):
            with Form(self.env["economic.branch"]) as form:
                form.name = "ZZ RAMA BASE"
        self.assertIsInstance(caught.exception, (ValidationError, IntegrityError))

    # --- economic.activity --------------------------------------------
    def _activity(self, code="ZZ-A1", municipality=None, aliquot=1.5):
        with Form(self.env["economic.activity"]) as form:
            form.name = code
            form.branch_id = self.branch
            form.municipality_id = municipality or self.municipality
            form.aliquot = aliquot
            form.minimum_monthly = 1.0
            form.minimum_annual = 12.0
            form.description = "ZZ"
        return form.save()

    def test_economic_activity_zero_aliquot_is_rejected(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._activity(aliquot=0.0)

    def test_economic_activity_duplicate_code_in_municipality_is_rejected(self):
        self._activity()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._activity()

    def test_economic_activity_same_code_other_municipality_is_allowed(self):
        first = self._activity()
        second = self._activity(municipality=self.other_municipality)
        self.assertNotEqual(first, second)

    # --- payment.concept.line -----------------------------------------
    def test_payment_concept_line_duplicate_code_is_rejected(self):
        concept = self.env["payment.concept"].create({"name": "ZZ Concepto"})
        person = self.env["type.person"].create({"name": "ZZ Persona"})
        vals = {"code": "ZZ-C1", "payment_concept_id": concept.id, "type_person_id": person.id}
        self.env["payment.concept.line"].create(dict(vals))
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["payment.concept.line"].create(dict(vals))
