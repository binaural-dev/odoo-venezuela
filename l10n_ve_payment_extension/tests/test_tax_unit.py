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

    def test_03_change_active_by_date_edit(self):
        """ Si muevo la fecha de la activa al pasado, la otra debe activarse """
       
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