import logging
from odoo.tests import tagged, TransactionCase, Form
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
        iva_sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia de iva para proveedores",
                "code": "payment.retention.iva",
                "prefix": "",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        bank_account = self.env["account.account"].search(
            [("account_type", "=", "liquidity")], limit=1
        )
        transitory_account = self.env["account.account"].search(
            [("account_type", "=", "other")], limit=1
        )
        profit_account = self.env["account.account"].search(
            [("account_type", "=", "income")], limit=1
        )
        loss_account = self.env["account.account"].search(
            [("account_type", "=", "expense")], limit=1
        )

        self.iva_journal = self.env["account.journal"].create(
            {
                "name": "Retenciones IVA",
                "code": "RETIVA",
                "type": "bank",
                "sequence_id": iva_sequence.id,
                "company_id": self.env.company.id,
                "bank_account_id": bank_account.id,
                "default_account_id": transitory_account.id,
                "profit_account_id": profit_account.id,
                "loss_account_id": loss_account.id,
            }
        )

        self.payment_method_inbound = self.env['account.payment.method'].create(
            {
                'name': 'Manual',
                'code': 12,
                'payment_type': 'inbound'
            }
        )

        self.payment_method_outbound = self.env['account.payment.method'].create(
            {
                'name': 'Manual',
                'code': 12,
                'payment_type': 'outbound'
            }
        )

        self.islr_supplier_retention_journal = self.env["account.journal"].create(
            {
                "name": "Retenciones ISLR PROVEEDOR",
                "code": "RTISLR",
                "type": "bank",
                "sequence_id": iva_sequence.id,
                "company_id": self.env.company.id,
                "bank_account_id": bank_account.id,
                "default_account_id": transitory_account.id,
                "profit_account_id": profit_account.id,
                "loss_account_id": loss_account.id,
                "inbound_payment_method_line_ids": [Command.create(
                    {
                        'payment_method_id':self.payment_method_inbound.id, 
                        'name': 'Manual'
                    }
                )],
                "outbound_payment_method_line_ids": [Command.create(
                    {
                        'payment_method_id': self.payment_method_outbound.id, 
                        'name': 'Manual'
                    }
                )],
            }
        )

        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
                "iva_supplier_retention_journal_id": self.iva_journal.id,
                "islr_supplier_retention_journal_id": self.islr_supplier_retention_journal.id
            }
        )

        self.tax_group_iva16 = self.env["account.tax.group"].create({"name": "IVA 16%"})

        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": self.tax_group_iva16.id,
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "service",
                "list_price": 100,
                "barcode": "123456789",
                "purchase_ok": True,
                "supplier_taxes_id": [(6, 0, [self.tax_iva16.id])],
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
            }
        )

        self.payment_concept = self.env["payment.concept"].create(
            {
                "name": "Test Payment Concept",
                "status": True,
            }
        )

        self.line_payment_concept = self.env["payment.concept.line"].create(
            {
                'type_person_id': self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id,
                'payment_concept_id': self.payment_concept.id,
                'code': 52,
                'percentage_tax_base': 100,
                'tariff_id': self.env.ref('l10n_ve_payment_extension.fees_retention_data_percentage_one_l10n_ve_payment_extension').id,
                'pay_from': 0.13,
            }
        )

        self.payment_concept.write({"line_payment_concept_ids": [(6, 0, [self.line_payment_concept.id])]})

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
                "type_person_id": self.env.ref('l10n_ve_payment_extension.type_person_l10n_ve_payment_extension').id,
                "withholding_type_id": self.env["account.withholding.type"]
                .search([("name", "=", "75%")], limit=1)
                .id,
            }
        )

        sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        refund_sequence = self.env["ir.sequence"].create(
            {
                "name": "nota de credito",
                "code": "",
                "prefix": "NC/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario de Ventas",
                "code": "VEN",
                "type": "purchase",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": self.env.company.id,
            }
        )

    def _create_invoice_simple(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "journal_id": self.journal.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 2,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_iva16.id])],
                            "price_subtotal": 200,
                            "price_total": 232,
                            "foreign_rate": 2.0,
                            "foreign_price": 200,
                            "foreign_subtotal": 400,
                            "foreign_price_total": 464,
                        },
                    ),
                ],
            }
        )

        return invoice

    def _create_retention(self, invoice,type_retention):
        today = fields.Date.today()

        _logger.warning("Creatingaction_post retention for invoice %s", invoice.amount_total)
        _logger.warning("Creating retention for invoice %s", invoice.amount_untaxed)
        with Form(self.env["account.retention"].with_context({"default_type":'in_invoice', "default_type_retention":'islr'})) as retention_form:
            retention_form.partner_id = self.partner_a
            retention_form.date_accounting = today

        retention = retention_form.save()

        with Form(retention) as retention_form_edit:
            with retention_form_edit.retention_line_ids.new() as line:
                line.move_id = invoice
                line.payment_concept_id = self.payment_concept

        retention = retention_form_edit.save()

        return retention

    def test_01_sequence_created_on_create_iva(self):
        invoice = self._create_invoice_simple()
        invoice.action_post()
        retention = self._create_retention(invoice,'iva')

        with self.assertRaises(ValidationError) as e:
            retention.action_post()
        self.assertIn(
            "IVA retention: Number must be exactly 14 numeric digits.", str(e.exception)
        )

    def test_02_generate_iva_retention_withholding_from_invoice(self):
        invoice = self._create_invoice_simple()
        invoice.generate_iva_retention = True
        invoice.action_post()
        retention = invoice.retention_iva_line_ids
        self.assertTrue(retention, "IVA retention should be created from the invoice.")
        _logger.info(
            "test_02_generate_iva_retention_withholding_from_invoice --- successfully."
        )

    def test_03_not_generate_iva_retention_withholding_from_invoice(self):
        invoice = self._create_invoice_simple()
        invoice.generate_iva_retention = False
        invoice.action_post()
        retention = invoice.retention_iva_line_ids
        self.assertTrue(
            not retention, "VAT withholding should not be made from the invoice."
        )
        _logger.info(
            "test_03_not_generate_iva_retention_withholding_from_invoice --- successfully."
        )

    def test_05_approve_islr_retention(self):
        """Try creating an invoice, withholding it, and approving it."""
        invoice = self._create_invoice_simple()
        invoice.action_post()

        retention = self._create_retention(invoice,'islr')
        retention.action_post()

        self.assertEqual(retention.state, 'emitted')
        _logger.info(
            "test_05_approve_islr_retention --- successfully."
        )
