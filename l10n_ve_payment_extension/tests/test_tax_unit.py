from odoo.tests import tagged , Form ,TransactionCase
from odoo.exceptions import UserError
from odoo import fields

@tagged('post_install', '-at_install', 'tax_unit')
class TestTaxUnit(TransactionCase):

    def setUp(self):
        super(TestTaxUnit, self).setUp()
        # 1. Creamos la Unidad Tributaria inicial (Será la activa por fecha)
        default_ut = self.env.ref('l10n_ve_accountant.tax_unit_data_l10n_ve_payment_extension', raise_if_not_found=False)
        if default_ut:
            # Usamos super() para saltar la validación de 'No puedes editar si no está activa'
            default_ut._write({'available_date': '1900-01-01'})
        
        with Form(self.env['tax.unit']) as f:
            f.name = "UT 2025"
            f.value = 100.0
            f.available_date = fields.Date.from_string('2025-01-01')
            self.ut_2025 = f.save()

        # 3. Creamos la Retención
        self.retention = self.env['fees.retention'].create({
            'name': 'Retención Test',
            'percentage': 3.0,
            'apply_subtracting': True,
            'status': True,
            'tax_unit_ids': self.ut_2025.id,
        })

    def test_01_form_constraints_duplicate(self):
        """ Validar que el Form dispara el UserError de duplicidad """
        # Intentar crear una con la misma fecha que ut_2025
        with self.assertRaises(UserError):
            with Form(self.env['tax.unit']) as f:
                f.name = "Duplicada"
                f.available_date = fields.Date.from_string('2025-01-01')
                f.value = 50.0
                f.save()
        
        with self.assertRaises(UserError):
            with Form(self.env['tax.unit']) as f:
                f.name = "Duplicada"
                f.available_date = fields.Date.from_string('2025-01-01')
                f.value = 100
                f.save()



    def test_02_automatic_status_and_calculation(self):
        """ Validar que al crear una nueva UT, la vieja se desactiva y el sustraendo cambia """
        # Valor esperado inicial: (100 * 83.3334 * 3 / 100) = 250.0002
        self.assertAlmostEqual(self.retention.amount_subtract, 250.0002, places=4)

        # Creamos UT 2026 (Nueva Activa)
        with Form(self.env['tax.unit']) as f:
            f.name = "UT 2026"
            f.value = 200.0
            f.available_date = fields.Date.from_string('2026-01-01')
            ut_2026 = f.save()

        retention = self.env['fees.retention'].browse(self.retention.id)  # Refrescar retención para obtener cambios
        # Verificamos cambio de estatus
        self.assertTrue(ut_2026.status)
        self.assertFalse(self.ut_2025.status)

        self.env.flush_all()
        self.env.invalidate_all()
        # Verificamos que la retención ahora apunta a la nueva y recalculó
        # Nuevo cálculo: (200 * 83.3334 * 3 / 100) = 500.0004

        self.assertEqual(retention.tax_unit_ids.id, ut_2026.id)
        self.assertAlmostEqual(retention.amount_subtract, 500.0004, places=4)

    def test_03_edit_value_recomputes_via_form(self):
        """ Editar el 'value' de la UT activa desde el Form recalcula el sustraendo """
        with Form(self.ut_2025) as f:
            f.value = 150.0
            f.save()

        self.env.flush_all()
        self.env.invalidate_all()

        self.assertAlmostEqual(self.retention.amount_subtract, 375.0003, places=4)

    def test_04_edit_value_active_updates_retention(self):
        """ Si cambio el 'value' de la unidad activa, el sustraendo de la tarifa debe actualizarse """
        self.ut_2025.write({'value': 150.0})
        
        # Nuevo cálculo: (150 * 83.3334 * 3 / 100) = 375.0003
        self.assertAlmostEqual(self.retention.amount_subtract, 375.0003, places=4)
        
        # Verificar que dejó mensaje en el chatter (mail.message)
        messages = self.env['mail.message'].search([
            ('model', '=', 'fees.retention'),
            ('res_id', '=', self.retention.id)
        ])
        self.assertTrue(len(messages) > 0, "Debería haber mensajes en el chatter de la retención")

    def test_05_prevent_edit_inactive(self):
        """ Prohibir edición de UT inactivas """
        # Creamos una para inactivar la actual
        self.env['tax.unit'].create({
            'name': 'UT Winner',
            'value': 1.0,
            'available_date': '2099-01-01',
        })
        self.assertFalse(self.ut_2025.status)

        # Intentar editar el valor de la inactiva debe lanzar UserError
        with self.assertRaises(UserError):
            self.ut_2025.write({'value': 500.0})

    def test_06_new_inactive_unit_created_after_active_one(self):
        """ Crear una UT con fecha PASADA (queda inactiva) después de la activa
        no debe pisar la tarifa con la UT inactiva, aunque su id sea mayor """
        # ut_2025 (id menor) queda activa por tener la fecha más reciente hasta ahora.
        with Form(self.env['tax.unit']) as f:
            f.name = "UT 2024"
            f.value = 999.0
            f.available_date = fields.Date.from_string('2024-01-01')
            ut_2024 = f.save()

        self.env.flush_all()
        self.env.invalidate_all()

        # ut_2024 tiene un id mayor que ut_2025 pero fecha anterior: debe quedar inactiva
        self.assertFalse(ut_2024.status)
        self.assertTrue(self.ut_2025.status)

        # La tarifa debe seguir apuntando a la UT activa (ut_2025), no a la recién creada
        retention = self.env['fees.retention'].browse(self.retention.id)
        self.assertEqual(retention.tax_unit_ids.id, self.ut_2025.id)
        self.assertAlmostEqual(retention.amount_subtract, 250.0002, places=4)

    def test_07_updates_all_fees_regardless_of_flags(self):
        """ La UT activa es única para todas las tarifas: debe propagarse
        aunque apply_subtracting sea False o la tarifa esté inactiva """
        other_retention = self.env['fees.retention'].create({
            'name': 'Retención sin sustraendo',
            'percentage': 1.0,
            'apply_subtracting': False,
            'status': True,
            'tax_unit_ids': self.ut_2025.id,
        })
        inactive_retention = self.env['fees.retention'].create({
            'name': 'Retención inactiva',
            'percentage': 2.0,
            'apply_subtracting': True,
            'status': False,
            'tax_unit_ids': self.ut_2025.id,
        })

        with Form(self.env['tax.unit']) as f:
            f.name = "UT 2026"
            f.value = 200.0
            f.available_date = fields.Date.from_string('2026-01-01')
            ut_2026 = f.save()

        self.env.flush_all()
        self.env.invalidate_all()

        other_retention.invalidate_recordset()
        inactive_retention.invalidate_recordset()

        self.assertEqual(other_retention.tax_unit_ids.id, ut_2026.id)
        self.assertEqual(inactive_retention.tax_unit_ids.id, ut_2026.id)

    def test_08_value_edit_updates_all_fees_regardless_of_flags(self):
        """ Cambiar el 'value' de la UT activa debe propagarse a TODAS las
        fees.retention existentes, sin importar apply_subtracting/status """
        other_retention = self.env['fees.retention'].create({
            'name': 'Retención sin sustraendo',
            'percentage': 1.0,
            'apply_subtracting': False,
            'status': True,
            'tax_unit_ids': self.ut_2025.id,
        })
        inactive_retention = self.env['fees.retention'].create({
            'name': 'Retención inactiva',
            'percentage': 2.0,
            'apply_subtracting': True,
            'status': False,
            'tax_unit_ids': self.ut_2025.id,
        })

        self.ut_2025.write({'value': 150.0})

        self.env.flush_all()
        self.env.invalidate_all()

        other_retention.invalidate_recordset()
        inactive_retention.invalidate_recordset()

        # Siguen apuntando a la misma UT (ninguna otra se creó), lo que importa
        # aquí es que el propio 'value' se propague al recompute de todas.
        self.assertEqual(other_retention.tax_unit_ids.id, self.ut_2025.id)
        self.assertEqual(inactive_retention.tax_unit_ids.id, self.ut_2025.id)
        # Con apply_subtracting=False el sustraendo siempre es 0, sin importar el value.
        self.assertEqual(other_retention.amount_subtract, 0)
        # Nuevo cálculo: (150 * 83.3334 * 2 / 100) = 250.0002
        self.assertAlmostEqual(inactive_retention.amount_subtract, 250.0002, places=4)

    def test_09_status_change_updates_all_fees_regardless_of_flags(self):
        """ Al cambiar cuál UT queda activa (vía available_date/status), todas
        las fees.retention deben terminar apuntando a la nueva activa,
        sin importar apply_subtracting/status """
        other_retention = self.env['fees.retention'].create({
            'name': 'Retención sin sustraendo',
            'percentage': 1.0,
            'apply_subtracting': False,
            'status': True,
            'tax_unit_ids': self.ut_2025.id,
        })
        inactive_retention = self.env['fees.retention'].create({
            'name': 'Retención inactiva',
            'percentage': 2.0,
            'apply_subtracting': True,
            'status': False,
            'tax_unit_ids': self.ut_2025.id,
        })

        ut_2026 = self.env['tax.unit'].create({
            'name': 'UT 2026',
            'value': 200.0,
            'available_date': '2026-01-01',
        })

        self.env.flush_all()
        self.env.invalidate_all()

        other_retention.invalidate_recordset()
        inactive_retention.invalidate_recordset()

        self.assertTrue(ut_2026.status)
        self.assertFalse(self.ut_2025.status)
        self.assertEqual(other_retention.tax_unit_ids.id, ut_2026.id)
        self.assertEqual(inactive_retention.tax_unit_ids.id, ut_2026.id)