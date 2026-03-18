from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError
from odoo import fields

@tagged('post_install', '-at_install')
class TestRetentionISLRTarifa2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestRetentionISLRTarifa2, cls).setUpClass()

        cls.company = cls.env.user.company_id
        cls.company.currency_id = cls.env.ref('base.VEF')
        
        # Activar el uso de retenciones de ISLR
        cls.env['ir.config_parameter'].sudo().set_param('l10n_ve_payment_extension.use_islr_retention', True)

        def find_or_create_account(name, code, account_type, reconcile=False):
            account = cls.env['account.account'].search([
                ('code', '=', code),
                ('company_ids', 'in', cls.company.id)
            ], limit=1)
            if not account:
                account = cls.env['account.account'].create({
                    'name': name,
                    'code': code,
                    'account_type': account_type,
                    'reconcile': reconcile,
                })
            return account

        # Crear cuenta de gastos
        cls.expense_account = find_or_create_account('Gastos Test', '600000', 'expense')
        
        # Crear cuentas por pagar y cobrar
        cls.payable_account = find_or_create_account('Payable Account', '2010101', 'liability_payable', True)
        cls.receivable_account = find_or_create_account('Receivable Account', '1010101', 'asset_receivable', True)

        # Crear diario de compras
        cls.purchase_journal = cls.env['account.journal'].create({
            'name': 'Compras Test',
            'code': 'PTJ',
            'type': 'purchase',
            'company_id': cls.env.company.id,
        })
        # Crear unidad tributaria de 43 Bs
        cls.tax_unit = cls.env['tax.unit'].create({
            'name': 'UT Test',
            'value': 43.0,
            'status': True,
        })

        # Crear tarifa acumulada para el concepto
        cls.tariff = cls.env['fees.retention'].create({
            'name': 'Tarifa 2 - PJND',
            'accumulated_rate': True,
            'amount_subtract': 0.0,
            'percentage': 15.0, # valor por defecto si no es acumulada, no importa aquí
            'tax_unit_ids': cls.tax_unit.id,
            'accumulated_rate_ids': [
                (0, 0, {
                    'name': 'Tramo 1',
                    'start': 0.0,
                    'stop': 2000.0,
                    'percentage': 15.0,
                    'subtract_ut': 0.0,
                }),
                (0, 0, {
                    'name': 'Tramo 2',
                    'start': 2000.0,
                    'stop': 3000.0,
                    'percentage': 22.0,
                    'subtract_ut': 140.0,
                }),
                (0, 0, {
                    'name': 'Tramo 3',
                    'start': 3000.0,
                    'stop': 0.0, # Infinito
                    'percentage': 34.0,
                    'subtract_ut': 500.0,
                })
            ]
        })

        # Crear tipo de persona PJND
        cls.type_person_pjnd = cls.env['type.person'].create({
            'name': 'Persona Jurídica No Domiciliada',
        })

        # Crear concepto de pago (Honorarios Profesionales)
        cls.payment_concept = cls.env['payment.concept'].create({
            'name': 'Honorarios Profesionales',
        })
        
        # Asociar la tarifa al concepto y tipo de persona (Base 90%)
        cls.env['payment.concept.line'].create({
            'payment_concept_id': cls.payment_concept.id,
            'type_person_id': cls.type_person_pjnd.id,
            'tariff_id': cls.tariff.id,
            'percentage_tax_base': 90.0,
            'pay_from': 0.0,
            'code': '001',
        })

        # Crear proveedor PJND
        cls.partner = cls.env['res.partner'].create({
            'name': 'Partner Test Tarifa 2',
            'is_company': True,
            'type_person_id': cls.type_person_pjnd.id,
            'country_id': cls.env.ref('base.us').id,
            'vat': 'J000000001',
            'property_account_payable_id': cls.payable_account.id,
            'property_account_receivable_id': cls.receivable_account.id,
        })

        # Crear producto
        cls.product = cls.env['product.product'].create({
            'name': 'Asesoría Técnica',
            'type': 'service',
            'list_price': 1.0, # No importa para compras
        })

    def test_retention_islr_tarifa_2_vef(self):
        """Probar el ejemplo del usuario con factura en Bolívares"""
        # Crear factura en Bolívares por 20.000 Bs
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.context_today(self.env.user),
            'currency_id': self.env.ref('base.VEF').id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'price_unit': 20000.0,
                'quantity': 1.0,
                'account_id': self.expense_account.id,
            })],
        })
        
        # Procesar los conceptos de pago de la factura, Odoo debería crear las líneas
        # de retención automáticamente si el módulo funciona así, o se hace manual.
        # Simulamos la creación manual de la línea que el usuario haría al procesar ISLR.
        
        retention = self.env['account.retention'].create({
            'partner_id': self.partner.id,
            'type_retention': 'islr',
            'type': 'in_invoice',
        })

        retention_line = self.env['account.retention.line'].create({
            'name': 'Retencion ISLR VEF',
            'retention_id': retention.id,
            'move_id': invoice.id,
            'payment_concept_id': self.payment_concept.id,
            'invoice_amount': 20000.0, # Base imponible
            'invoice_total': 20000.0,
            'foreign_invoice_total': 20000.0,
            'retention_amount': 1.0,
            'foreign_retention_amount': 1.0,
        })

        # Forzar los cómputos
        retention_line._compute_related_fields()
        retention_line._compute_retention_amount()

        # Verificar los cálculos
        # Base VEF: 20000
        # Base UT: 20000 / 43 = 465.12
        # UT Aplicables (90%): 465.12 * 0.90 = 418.61 (Tramo 1: 15%)
        # Retención UT: 418.61 * 0.15 = 62.79
        # Retención VEF: 62.79 * 43 = 2699.97

        self.assertEqual(retention_line.related_percentage_fees, 15.0, "La tarifa seleccionada debe ser del 15% (Tramo 1)")
        self.assertAlmostEqual(retention_line.retention_amount, 2699.97, places=2, msg="La retención en VEF no es la esperada.")

    def test_retention_islr_tarifa_2_tramo_2(self):
        """Probar el Tramo 2 (2001 - 3000 U.T.) al 22% con sustraendo de 140 U.T."""
        # Se necesita una base retenible (90% del subtotal) que caiga entre 2001 y 3000 UT.
        # Si Base Retenible = 2500 UT -> Base Total (100%) en UT = 2500 / 0.9 = 2777.77 UT
        # Monto VEF = 2777.77 UT * 43 Bs/UT = 119444.44 Bs
        
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.context_today(self.env.user),
            'currency_id': self.env.ref('base.VEF').id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'price_unit': 119444.44,
                'quantity': 1.0,
                'account_id': self.expense_account.id,
            })],
        })
        
        retention = self.env['account.retention'].create({
            'partner_id': self.partner.id,
            'type_retention': 'islr',
            'type': 'in_invoice',
        })

        retention_line = self.env['account.retention.line'].create({
            'name': 'Retencion ISLR T2',
            'retention_id': retention.id,
            'move_id': invoice.id,
            'payment_concept_id': self.payment_concept.id,
            'invoice_amount': 119444.44,
            'invoice_total': 119444.44,
            'foreign_invoice_total': 119444.44,
            'retention_amount': 1.0,
            'foreign_retention_amount': 1.0,
        })

        retention_line._compute_related_fields()
        retention_line._compute_retention_amount()

        # Cálculo esperado:
        # Base VEF: 119444.44
        # Base UT: 119444.44 / 43 = 2777.78 UT
        # UT Aplicables (90%): 2777.78 * 0.90 = 2500.00 UT (Cae en Tramo 2: 2001 a 3000)
        # Retención UT (22%): 2500.00 * 0.22 = 550.00 UT
        # Sustraendo UT: 140.00
        # Total Retención UT: 550.00 - 140.00 = 410.00 UT
        # Retención VEF: 410.00 * 43 = 17630.00 Bs
        
        self.assertEqual(retention_line.related_percentage_fees, 22.0, "La tarifa debe ser 22% (Tramo 2)")
        self.assertEqual(retention_line.related_amount_subtract_fees, 140.0 * 43.0, "El sustraendo debe ser 6020 Bs (140 UT)")
        self.assertAlmostEqual(retention_line.retention_amount, 17630.00, places=2)

    def test_retention_islr_tarifa_2_tramo_3(self):
        """Probar el Tramo 3 (Más de 3000 U.T.) al 34% con sustraendo de 500 U.T."""
        # Se necesita una base retenible (90% del subtotal) mayor a 3000 UT.
        # Si Base Retenible = 4000 UT -> Base Total (100%) en UT = 4000 / 0.9 = 4444.44 UT
        # Monto VEF = 4444.44 UT * 43 Bs/UT = 191111.11 Bs
        
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': fields.Date.context_today(self.env.user),
            'currency_id': self.env.ref('base.VEF').id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'price_unit': 191111.11,
                'quantity': 1.0,
                'account_id': self.expense_account.id,
            })],
        })
        
        retention = self.env['account.retention'].create({
            'partner_id': self.partner.id,
            'type_retention': 'islr',
            'type': 'in_invoice',
        })

        retention_line = self.env['account.retention.line'].create({
            'name': 'Retencion ISLR T3',
            'retention_id': retention.id,
            'move_id': invoice.id,
            'payment_concept_id': self.payment_concept.id,
            'invoice_amount': 191111.11,
            'invoice_total': 191111.11,
            'foreign_invoice_total': 191111.11,
            'retention_amount': 1.0,
            'foreign_retention_amount': 1.0,
        })

        retention_line._compute_related_fields()
        retention_line._compute_retention_amount()

        # Cálculo esperado:
        # Base VEF: 191111.11
        # Base UT: 191111.11 / 43 = 4444.44 UT
        # UT Aplicables (90%): 4444.44 * 0.90 = 4000.00 UT (Cae en Tramo 3: Más de 3000)
        # Retención UT (34%): 4000.00 * 0.34 = 1360.00 UT
        # Sustraendo UT: 500.00
        # Total Retención UT: 1360.00 - 500.00 = 860.00 UT
        # Retención VEF: 860.00 * 43 = 36980.00 Bs
        
        self.assertEqual(retention_line.related_percentage_fees, 34.0, "La tarifa debe ser 34% (Tramo 3)")
        self.assertEqual(retention_line.related_amount_subtract_fees, 500.0 * 43.0, "El sustraendo debe ser 21500 Bs (500 UT)")
        self.assertAlmostEqual(retention_line.retention_amount, 36980.00, places=2)
        
