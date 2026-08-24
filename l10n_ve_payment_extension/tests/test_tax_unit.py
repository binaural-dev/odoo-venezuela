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

    def test_03_edit_value_via_form_updates_retention(self):
        """ Editar 'value' de la UT activa vía Form debe recalcular el sustraendo """

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

    def test_06_apply_subtracting_false_updates_tax_unit_ids(self):
        """
        apply_subtracting=False: al cambiar la UT activa, tax_unit_ids
        debe actualizarse (bug #13821 - faltaba este escenario)
        """
        retention_no_sub = self.env['fees.retention'].create({
            'name': 'Retención sin sustraendo',
            'percentage': 5.0,
            'apply_subtracting': False,
            'status': True,
            'tax_unit_ids': self.ut_2025.id,
        })

        self.assertEqual(retention_no_sub.tax_unit_ids.id, self.ut_2025.id)
        self.assertEqual(retention_no_sub.amount_subtract, 0.0)

        with Form(self.env['tax.unit']) as f:
            f.name = "UT 2026"
            f.value = 200.0
            f.available_date = fields.Date.from_string('2026-01-01')
            ut_2026 = f.save()

        retention_no_sub.invalidate_recordset()
        self.assertEqual(
            retention_no_sub.tax_unit_ids.id,
            ut_2026.id,
            "tax_unit_ids debe actualizarse aunque apply_subtracting=False"
        )
        self.assertEqual(retention_no_sub.amount_subtract, 0.0)

    def test_07_national_value_must_match_across_companies(self):
        """
        La UT es nacional: dos tax.unit con la misma available_date deben
        tener el mismo value sin importar la compañía. Un valor divergente
        para la misma fecha debe rechazarse (evita que fees.retention, que
        es global, quede corrupta por una UT de compañía distinta).
        """
        other_company = self.env['res.company'].create({'name': 'Otra Compañía UT'})

        with self.assertRaises(UserError):
            self.env['tax.unit'].with_company(other_company).create({
                'name': 'UT Otra Compañía Divergente',
                'value': 999.0,
                'available_date': self.ut_2025.available_date,
                'company_id': other_company.id,
            })

        other_ut = self.env['tax.unit'].with_company(other_company).create({
            'name': 'UT Otra Compañía Igual',
            'value': self.ut_2025.value,
            'available_date': self.ut_2025.available_date,
            'company_id': other_company.id,
        })
        self.assertEqual(other_ut.value, self.ut_2025.value)
        self.assertEqual(other_ut.available_date, self.ut_2025.available_date)

    def test_08_active_status_scoped_per_company(self):
        """
        _update_active_status debe elegir "la más reciente" por compañía,
        no globalmente: la UT activa de una compañía no puede desactivar
        la UT activa de otra.
        """
        other_company = self.env['res.company'].create({'name': 'Otra Compañía UT Status'})

        other_ut_old = self.env['tax.unit'].with_company(other_company).create({
            'name': 'UT Otra Compañía Vieja',
            'value': 10.0,
            'available_date': '2020-01-01',
            'company_id': other_company.id,
        })
        self.assertTrue(other_ut_old.status)

        # UT más reciente en la compañía original: no debe tocar el status
        # de la UT activa de la otra compañía.
        self.env['tax.unit'].create({
            'name': 'UT Winner Compañía Original',
            'value': 1.0,
            'available_date': '2099-01-01',
        })

        other_ut_old.invalidate_recordset()
        self.assertTrue(
            other_ut_old.status,
            "La UT activa de otra compañía no debe desactivarse por un cambio ajeno"
        )

    def test_09_change_active_by_date_edit(self):
        """
        Escenario real del ticket 13821: editar available_date de la UT
        activa hacia una fecha anterior a otra UT existente debe reactivar
        esa otra UT, y TODAS las tarifas activas (con y sin sustraendo)
        deben quedar apuntando a la nueva activa.
        """
        retention_no_sub = self.env['fees.retention'].create({
            'name': 'Retención sin sustraendo (fecha)',
            'percentage': 5.0,
            'apply_subtracting': False,
            'status': True,
            'tax_unit_ids': self.ut_2025.id,
        })

        ut_older = self.env['tax.unit'].create({
            'name': 'UT Vieja',
            'value': 50.0,
            'available_date': '2020-01-01',
        })
        self.assertFalse(ut_older.status)

        self.ut_2025.write({'available_date': '2010-01-01'})

        self.env.flush_all()
        self.env.invalidate_all()

        self.assertFalse(self.ut_2025.status)
        self.assertTrue(ut_older.status)

        self.assertEqual(self.retention.tax_unit_ids.id, ut_older.id)
        self.assertEqual(retention_no_sub.tax_unit_ids.id, ut_older.id)
        self.assertAlmostEqual(self.retention.amount_subtract, 50.0 * 83.3334 * 3 / 100, places=4)
        self.assertEqual(retention_no_sub.amount_subtract, 0.0)

    def test_10_edit_value_updates_retention_without_subtract(self):
        """
        Escenario real del ticket 13821 pt.3: cambiar 'value' de la UT
        activa debe notificar/recalcular también las tarifas sin
        sustraendo, no solo las que tienen apply_subtracting=True.
        """
        retention_no_sub = self.env['fees.retention'].create({
            'name': 'Retención sin sustraendo (value)',
            'percentage': 5.0,
            'apply_subtracting': False,
            'status': True,
            'tax_unit_ids': self.ut_2025.id,
        })

        self.ut_2025.write({'value': 150.0})

        messages = self.env['mail.message'].search([
            ('model', '=', 'fees.retention'),
            ('res_id', '=', retention_no_sub.id),
        ])
        self.assertTrue(
            len(messages) > 0,
            "La tarifa sin sustraendo también debe recibir la notificación al cambiar 'value'"
        )
        self.assertEqual(retention_no_sub.tax_unit_ids.id, self.ut_2025.id)
        self.assertEqual(retention_no_sub.amount_subtract, 0.0)