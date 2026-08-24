import importlib.util
import os

from odoo.tests import tagged, TransactionCase


def _load_migrate():
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "19.0.2.0.26", "pre-migration.py"
    )
    spec = importlib.util.spec_from_file_location("l10n_ve_payment_extension_migration_19_0_2_0_26", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged('post_install', '-at_install', 'tax_unit')
class TestMigration19_0_2_0_26(TransactionCase):

    def setUp(self):
        super().setUp()
        self.migrate = _load_migrate()
        self.other_company = self.env['res.company'].create({'name': 'Otra Compañía UT'})

    def _create_orphan_tax_unit(self):
        # company_id es NOT NULL en el esquema actual; se relaja momentáneamente para
        # simular el estado de una base vieja, previo a que el ORM agregue la restricción.
        self.cr.execute("ALTER TABLE tax_unit ALTER COLUMN company_id DROP NOT NULL")
        self.cr.execute("""
            INSERT INTO tax_unit (name, value, status, available_date, company_id)
            VALUES ('UT huérfana', 0.4, true, '2024-01-01', NULL)
            RETURNING id
        """)
        return self.cr.fetchone()[0]

    def test_orphan_tax_unit_is_duplicated_per_company(self):
        """ Un tax.unit sin compañía debe replicarse en todas las compañías, no solo en una. """
        orphan_id = self._create_orphan_tax_unit()

        self.cr.execute("SELECT id FROM res_company ORDER BY id")
        company_ids = [row[0] for row in self.cr.fetchall()]
        self.assertGreaterEqual(len(company_ids), 2, "El test necesita al menos dos compañías")

        self.migrate(self.cr, "19.0.2.0.26")

        self.cr.execute("""
            SELECT company_id FROM tax_unit
            WHERE name = 'UT huérfana' AND value = 0.4 AND available_date = '2024-01-01'
        """)
        result_company_ids = sorted(row[0] for row in self.cr.fetchall())

        self.assertEqual(
            result_company_ids,
            sorted(company_ids),
            "Debe existir una copia de la UT huérfana por cada compañía",
        )
        self.cr.execute("SELECT COUNT(*) FROM tax_unit WHERE company_id IS NULL")
        self.assertEqual(self.cr.fetchone()[0], 0, "No deben quedar tax_unit sin compañía")

    def test_no_orphans_is_noop(self):
        """ Si no hay tax_unit huérfanos, el migrate no debe crear registros nuevos. """
        self.cr.execute("SELECT COUNT(*) FROM tax_unit")
        before = self.cr.fetchone()[0]

        self.migrate(self.cr, "19.0.2.0.26")

        self.cr.execute("SELECT COUNT(*) FROM tax_unit")
        after = self.cr.fetchone()[0]
        self.assertEqual(before, after)

    def test_migrate_is_idempotent_on_rerun(self):
        """
        Correr migrate() dos veces sobre los mismos datos no debe duplicar
        copias por compañía (la migración no es transaccionalmente atómica
        con el resto de la actualización, así que puede reintentarse).
        """
        orphan_id = self._create_orphan_tax_unit()

        self.cr.execute("SELECT id FROM res_company ORDER BY id")
        company_ids = [row[0] for row in self.cr.fetchall()]

        self.migrate(self.cr, "19.0.2.0.26")
        self.cr.execute("""
            SELECT COUNT(*) FROM tax_unit
            WHERE name = 'UT huérfana' AND value = 0.4 AND available_date = '2024-01-01'
        """)
        count_after_first_run = self.cr.fetchone()[0]
        self.assertEqual(count_after_first_run, len(company_ids))

        # Re-ejecutar con los mismos huérfanos ya migrados (ahora ya tienen
        # company_id, así que el segundo run no debería encontrar huérfanos
        # nuevos ni insertar copias adicionales).
        self.migrate(self.cr, "19.0.2.0.26")
        self.cr.execute("""
            SELECT COUNT(*) FROM tax_unit
            WHERE name = 'UT huérfana' AND value = 0.4 AND available_date = '2024-01-01'
        """)
        count_after_second_run = self.cr.fetchone()[0]
        self.assertEqual(
            count_after_second_run, count_after_first_run,
            "Un segundo run no debe duplicar las copias ya migradas",
        )
