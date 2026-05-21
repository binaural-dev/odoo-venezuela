import logging
from odoo.tests import tagged, TransactionCase
from odoo import Command, fields
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "account_move", "retention_unlink")
class TestAccountMove(TransactionCase):
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

        self.islr_journal = self.env["account.journal"].create(
            {
                "name": "Retenciones ISLR",
                "code": "RETISLR",
                "type": "bank",
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
                "islr_supplier_retention_journal_id": self.islr_journal.id,
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

        self.tax_unit = self.env["tax.unit"].search([('name', '=', 'Test Tax Unit 2025')], limit=1) or \
        self.env["tax.unit"].create({"name": "Test Tax Unit 2025", "value": 9.0, "status": True})

        self.type_person = self.env["type.person"].create(
            {
                "name": "PN Residente",
                "state": True,
            }
        )

        self.islr_tariff = self.env["fees.retention"].search([('name', '=', 'Test Tariff 3%')], limit=1) or \
                          self.env["fees.retention"].create({"name": "Test Tariff 3%", "percentage": 3.0, "tax_unit_ids": self.tax_unit.id})

        self.payment_concept = self.env["payment.concept"].search([('name', '=', 'Test ISLR Concept')], limit=1) or \
        self.env["payment.concept"].create({
            "name": "Test ISLR Concept",
            "line_payment_concept_ids": [(0, 0, {
                "code": "ISLR-TEST-CODE", "type_person_id": self.type_person.id,
                "percentage_tax_base": 100.0, "tariff_id": self.islr_tariff.id,
            })],
        })

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
                            "payment_concept_id": self.payment_concept.id,
                        }
                    )
                ],
            }
        )

    def test_01_unlink_invoice_with_emitted_retention_iva(self):
        invoice = self._create_invoice_simple()
        invoice.generate_iva_retention = True
        invoice.action_post()
        retention = invoice.retention_iva_line_ids
        self.assertTrue(invoice.retention_iva_line_ids, "IVA retention should be created from the invoice.")
        
        with self.assertRaises(UserError) as e:
            invoice.button_draft()
            invoice.unlink()
        self.assertIn("You cannot delete an invoice with an emitted retention", str(e.exception))        

        _logger.info("test_01_unlink_invoice_with_emitted_retention_iva --- successfully.")

    def test_02_unlink_invoice_with_emitted_retention_iva_cancelled(self):
        invoice = self._create_invoice_simple()
        invoice.generate_iva_retention = True
        invoice.action_post()
        retention = invoice.retention_iva_line_ids
        self.assertTrue(retention, "IVA retention should be created from the invoice.")
        retention.retention_id.action_cancel()
        invoice.button_draft()
        invoice.unlink()

        _logger.info("test_02_unlink_invoice_with_emitted_retention_iva_cancelled --- successfully.")

    def test_03_unlink_invoice_without_emitted_retention_islr(self):
        invoice = self._create_invoice_simple()
        invoice.action_post()
        retention = self.env["account.retention"].create(
            {
                "type_retention": "islr",
                "type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "date": fields.Date.today(),
                "date_accounting": fields.Date.today(),
                "retention_line_ids": [
                    Command.create(
                        {
                            "move_id": invoice.id,
                            "name": "Test ISLR Retention Line",
                            "invoice_total": invoice.amount_total,
                            "invoice_amount": invoice.amount_untaxed,
                            "payment_concept_id": self.payment_concept.id,
                            "retention_amount": float_round(
                                invoice.amount_untaxed * 0.03, precision_rounding=0.01
                            ),
                            "foreign_retention_amount": float_round(
                                invoice.amount_untaxed * 0.03, precision_rounding=0.01
                            ),
                            "foreign_invoice_amount": invoice.amount_untaxed,
                        }
                    )
                ],
            }
        )
        retention.invalidate_recordset()
        retention.action_post()
        self.assertTrue(invoice.retention_islr_line_ids, "ISLR retention should be created from the invoice.")
        
        with self.assertRaises(UserError) as e:
            invoice.button_draft()
            invoice.unlink()
        self.assertIn("You cannot delete an invoice with an emitted retention", str(e.exception))        

        _logger.info("test_03_unlink_invoice_without_emitted_retention_islr --- successfully.")

    def test_04_unlink_invoice_without_emitted_retention_islr_cancelled(self):
        invoice = self._create_invoice_simple()
        invoice.action_post()
        retention = self.env["account.retention"].create(
            {
                "type_retention": "islr",
                "type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "date": fields.Date.today(),
                "date_accounting": fields.Date.today(),
                "retention_line_ids": [
                    Command.create(
                        {
                            "move_id": invoice.id,
                            "name": "Test ISLR Retention Line",
                            "invoice_total": invoice.amount_total,
                            "invoice_amount": invoice.amount_untaxed,
                            "payment_concept_id": self.payment_concept.id,
                            "retention_amount": float_round(
                                invoice.amount_untaxed * 0.03, precision_rounding=0.01
                            ),
                            "foreign_retention_amount": float_round(
                                invoice.amount_untaxed * 0.03, precision_rounding=0.01
                            ),
                            "foreign_invoice_amount": invoice.amount_untaxed,
                        }
                    )
                ],
            }
        )
        retention.invalidate_recordset()
        retention.action_post()
        retention.action_cancel()
        invoice.button_draft()
        invoice.unlink()

        _logger.info("test_04_unlink_invoice_without_emitted_retention_islr_cancelled --- successfully.")

    def test_05_unlink_invoice_with_emitted_retention_municipal(self):
        invoice = self._create_invoice_simple()
        invoice.action_post()
        retention = self.env["account.retention"].create(
            {
                "type_retention": "municipal",
                "type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "date": fields.Date.today(),
                "date_accounting": fields.Date.today(),
                "retention_line_ids": [
                    Command.create(
                        {
                            "move_id": invoice.id,
                            "name": "Test Municipal Retention Line",
                            "invoice_total": invoice.amount_total,
                            "invoice_amount": invoice.amount_untaxed,
                            "payment_concept_id": self.payment_concept.id,
                            "retention_amount": float_round(
                                invoice.amount_untaxed * 0.05, precision_rounding=0.01
                            ),
                            "foreign_retention_amount": float_round(
                                invoice.amount_untaxed * 0.05, precision_rounding=0.01
                            ),
                            "foreign_invoice_amount": invoice.amount_untaxed,
                        }
                    )
                ],
            }
        )
        retention.invalidate_recordset()
        retention.action_post()
        self.assertTrue(invoice.retention_municipal_line_ids, "Municipal retention should be created from the invoice.")
        
        with self.assertRaises(UserError) as e:
            invoice.button_draft()
            invoice.unlink()
        self.assertIn("You cannot delete an invoice with an emitted retention", str(e.exception))        

        _logger.info("test_05_unlink_invoice_with_emitted_retention_municipal --- successfully.")

    def test_06_unlink_invoice_with_emitted_retention_municipal_cancelled(self):
        invoice = self._create_invoice_simple()
        invoice.action_post()
        retention = self.env["account.retention"].create(
            {
                "type_retention": "municipal",
                "type": "in_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner_a.id,
                "date": fields.Date.today(),
                "date_accounting": fields.Date.today(),
                "retention_line_ids": [
                    Command.create(
                        {
                            "move_id": invoice.id,
                            "name": "Test Municipal Retention Line",
                            "invoice_total": invoice.amount_total,
                            "invoice_amount": invoice.amount_untaxed,
                            "payment_concept_id": self.payment_concept.id,
                            "retention_amount": float_round(
                                invoice.amount_untaxed * 0.05, precision_rounding=0.01
                            ),
                            "foreign_retention_amount": float_round(
                                invoice.amount_untaxed * 0.05, precision_rounding=0.01
                            ),
                            "foreign_invoice_amount": invoice.amount_untaxed,
                        }
                    )
                ],
            }
        )
        retention.invalidate_recordset()
        retention.action_post()
        retention.action_cancel()
        invoice.button_draft()
        invoice.unlink()

        _logger.info("test_06_unlink_invoice_with_emitted_retention_municipal_cancelled --- successfully.")