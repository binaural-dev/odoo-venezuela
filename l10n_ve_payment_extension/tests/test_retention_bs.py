import logging
from odoo.tests import tagged, TransactionCase
from odoo import Command, fields
from odoo.tools.float_utils import float_round
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_sequence")
class TestAccountRetentionSequence(TransactionCase):
    def setUp(self):
        super().setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
            }
        )

        self.tax_group_iva16 = self.env["account.tax.group"].create({"name": "IVA 16%"})
        self.tax_iva16 = self.env['account.tax'].create({
            'name': 'IVA 16%',
            'amount': 16,
            'amount_type': 'percent',
            'type_tax_use': 'purchase',
        })

        self.product = self.env['product.product'].create({
            'name': 'Producto Prueba',
            'type': 'service',
            'list_price': 100,
            'barcode': '123456789',
            'taxes_id': [(6, 0, [self.tax_iva16.id])],
        })

        self.partner_a = self.env['res.partner'].create({
            'name': 'Test Partner A',
            'customer_rank': 1,
        })

        sequence = self.env['ir.sequence'].create({
            'name': 'Secuencia Factura',
            'code': 'account.move',
            'prefix': 'INV/',
            'padding': 8,
            "number_next_actual": 2,
        })
        refund_sequence = self.env['ir.sequence'].create({
            'name': 'nota de credito',
            'code': '',
            'prefix': 'NC/',
            'padding': 8,
            "number_next_actual": 2,
        })

        self.journal = self.env['account.journal'].create({
            'name': 'Diario de Ventas',
            'code': 'VEN',
            'type': 'purchase',
            'sequence_id': sequence.id,
            "refund_sequence_id": refund_sequence.id,
            'company_id': self.env.company.id,
        })

    def _create_invoice_simple(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": self.journal.id,
                'invoice_date': fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_iva16.id])],
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _create_retention(self, invoice):
        today = fields.Date.today()
        payment_concept = self.env['payment.concept'].create({
            'name': 'Test Payment Concept',
        })

        _logger.warning("Creating retention for invoice %s", invoice.amount_total)
        _logger.warning("Creating retention for invoice %s", invoice.amount_untaxed)
        return self.env["account.retention"].create(
            {
                "type_retention": "iva",
                "type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "date": today,
                "date_accounting": today,
                "retention_line_ids": [
                    Command.create(
                        {
                            "move_id": invoice.id,
                            "name": "Test Retention Line",
                            "invoice_total": invoice.amount_total,
                            "invoice_amount": invoice.amount_untaxed,
                            'retention_amount': float_round(
                                invoice.amount_untaxed * 0.16, precision_rounding=0.01
                            ),
                            'foreign_retention_amount': float_round(
                                invoice.amount_untaxed * 0.16, precision_rounding=0.01
                            ),
                            'foreign_invoice_amount': invoice.amount_untaxed,
                            'payment_concept_id': payment_concept.id,
                        }
                    )
                ],
            })


    def test_sequence_created_on_create_iva(self):
        invoice = self._create_invoice_simple()
        retention = self._create_retention(invoice)
        retention.number = '0123456789'
        retention.type_retention = 'iva'
        
        with self.assertRaises(ValidationError) as e:
            retention.action_post()
        self.assertIn("IVA retention: Number must be exactly 14 numeric digits.", str(e.exception))
