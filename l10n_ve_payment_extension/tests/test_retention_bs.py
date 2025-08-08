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
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
                "iva_supplier_retention_journal_id": self.iva_journal.id,
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

        self.type_person = self.env["type.person"].create(
            {
                "name": "PN Residente",
                "state": True,
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
                "type_person_id": self.type_person.id,
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

    def _create_retention(self, invoice):
        today = fields.Date.today()
        payment_concept = self.env["payment.concept"].create(
            {
                "name": "Test Payment Concept",
            }
        )

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
                            "retention_amount": float_round(
                                invoice.amount_untaxed * 0.16, precision_rounding=0.01
                            ),
                            "foreign_retention_amount": float_round(
                                invoice.amount_untaxed * 0.16, precision_rounding=0.01
                            ),
                            "foreign_invoice_amount": invoice.amount_untaxed,
                            "payment_concept_id": payment_concept.id,
                        }
                    )
                ],
            }
        )

    def test_01_sequence_created_on_create_iva(self):
        invoice = self._create_invoice_simple()
        invoice.action_post()
        retention = self._create_retention(invoice)
        retention.number = "0123456789"
        retention.type_retention = "iva"

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
