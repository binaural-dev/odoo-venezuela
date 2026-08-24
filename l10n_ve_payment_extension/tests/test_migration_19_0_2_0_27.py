import importlib.util
import os

from odoo.tests import tagged, TransactionCase


def _load_migrate():
    path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "19.0.2.0.27", "post-migration.py"
    )
    spec = importlib.util.spec_from_file_location("l10n_ve_payment_extension_migration_19_0_2_0_27", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged('post_install', '-at_install', 'tax_unit')
class TestMigration19_0_2_0_27(TransactionCase):

    def setUp(self):
        super().setUp()
        self.migrate = _load_migrate()
        self.other_company = self.env['res.company'].create({'name': 'Otra Compañía Fees'})

        self.cr.execute("SELECT id FROM res_company ORDER BY id")
        self.company_ids = [row[0] for row in self.cr.fetchall()]
        self.first_company_id = self.company_ids[0]

        self.tax_unit = self.env['tax.unit'].create({
            'name': 'UT Migración Test',
            'value': 100.0,
            'available_date': '2030-01-01',
        })

    def _create_fees_retention_in_first_company(self, name, with_accumulated=False):
        # Simula el estado post-upgrade: el campo company_id es nuevo y el
        # ORM ya asignó todas las filas existentes a la primera compañía
        # (la que estaba activa durante el upgrade).
        fees = self.env['fees.retention'].create({
            'name': name,
            'percentage': 3.0,
            'apply_subtracting': False,
            'status': True,
            'company_id': self.first_company_id,
            'tax_unit_ids': self.tax_unit.id,
        })
        if with_accumulated:
            self.env['accumulated.fees'].create({
                'name': 'Tramo 1',
                'start': 0.0,
                'stop': 1000.0,
                'percentage': 3.0,
                'fees_id': fees.id,
            })
        return fees

    def test_fees_retention_is_duplicated_per_company(self):
        """ Una tarifa de la primera compañía debe replicarse en las demás. """
        fees = self._create_fees_retention_in_first_company('Tarifa Migración Test')

        self.migrate(self.cr, "19.0.2.0.27")

        self.cr.execute(
            "SELECT company_id FROM fees_retention WHERE name = %s",
            ('Tarifa Migración Test',),
        )
        result_company_ids = sorted(row[0] for row in self.cr.fetchall())

        self.assertEqual(
            result_company_ids,
            sorted(self.company_ids),
            "Debe existir una copia de la tarifa por cada compañía",
        )

    def test_accumulated_fees_lines_are_duplicated_with_their_parent(self):
        """
        Las líneas de accumulated.fees de una tarifa acumulada deben
        duplicarse junto con su tarifa, apuntando a la copia nueva
        (fees_id es Many2one, no pueden compartirse entre compañías).
        """
        fees = self._create_fees_retention_in_first_company(
            'Tarifa Acumulada Migración', with_accumulated=True
        )

        self.migrate(self.cr, "19.0.2.0.27")

        self.cr.execute(
            "SELECT id, company_id FROM fees_retention WHERE name = %s",
            ('Tarifa Acumulada Migración',),
        )
        rows = self.cr.fetchall()
        self.assertEqual(len(rows), len(self.company_ids))

        for fees_id, company_id in rows:
            self.cr.execute(
                "SELECT COUNT(*) FROM accumulated_fees WHERE fees_id = %s",
                (fees_id,),
            )
            self.assertEqual(
                self.cr.fetchone()[0], 1,
                "Cada copia de la tarifa debe tener su propia línea acumulada",
            )

    def test_no_source_rows_is_noop(self):
        """ Si no hay tarifas en la primera compañía, el migrate no crea nada. """
        # El módulo carga tarifas de demo en la primera compañía; se limpian
        # para simular una base sin ninguna fees.retention todavía.
        self.env['fees.retention'].search([('company_id', '=', self.first_company_id)]).unlink()

        self.cr.execute("SELECT COUNT(*) FROM fees_retention")
        before = self.cr.fetchone()[0]

        self.migrate(self.cr, "19.0.2.0.27")

        self.cr.execute("SELECT COUNT(*) FROM fees_retention")
        after = self.cr.fetchone()[0]
        self.assertEqual(before, after)

    def test_migrate_is_idempotent_on_rerun(self):
        """
        Correr migrate() dos veces sobre los mismos datos no debe duplicar
        copias por compañía.
        """
        self._create_fees_retention_in_first_company('Tarifa Idempotencia Test')

        self.migrate(self.cr, "19.0.2.0.27")
        self.cr.execute(
            "SELECT COUNT(*) FROM fees_retention WHERE name = %s",
            ('Tarifa Idempotencia Test',),
        )
        count_after_first_run = self.cr.fetchone()[0]
        self.assertEqual(count_after_first_run, len(self.company_ids))

        self.migrate(self.cr, "19.0.2.0.27")
        self.cr.execute(
            "SELECT COUNT(*) FROM fees_retention WHERE name = %s",
            ('Tarifa Idempotencia Test',),
        )
        count_after_second_run = self.cr.fetchone()[0]
        self.assertEqual(
            count_after_second_run, count_after_first_run,
            "Un segundo run no debe duplicar las copias ya migradas",
        )
