import logging

from odoo.tests.common import TransactionCase, tagged
from odoo import Command, fields
from odoo.tools.float_utils import float_round
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_sequence")
class TestAccountRetention(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "foreign_currency_id": self.currency_vef.id,
            }
        )

        self.liquidity_account = self.env["account.account"].create(
            {
                "name": "Banco Retenciones",
                "code": "101999",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.retention_journal = self.env["account.journal"].create(
            {
                "name": "Diario Retenciones",
                "type": "bank",
                "code": "RETEN",
                "company_id": self.company.id,
                "autocheck_on_post": True,
            }
        )
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        manual_out = self.env.ref("account.account_payment_method_manual_out")
        self.inbound_method_line = self.env["account.payment.method.line"].create(
            {
                "name": "Manual IN",
                "journal_id": self.retention_journal.id,
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
                "sequence": 10,
                "company_id": self.company.id,
                "payment_account_id": self.liquidity_account.id,

            }
        )
        self.outbound_method_line = self.env["account.payment.method.line"].create(
            {
                "name": "Manual OUT",
                "journal_id": self.retention_journal.id,
                "payment_method_id": manual_out.id,
                "payment_type": "outbound",
                "sequence": 10,
                "company_id": self.company.id,
                "payment_account_id": self.liquidity_account.id,

            }
        )
        self.retention_journal.write(
            {
                "inbound_payment_method_line_ids": [(6, 0, [self.inbound_method_line.id])],
                "outbound_payment_method_line_ids": [(6, 0, [self.outbound_method_line.id])],
            }
        )

        self.purchase_journal = self.env["account.journal"].create(
            {
                "name": "Purchase Journal",
                "code": "PUR",
                "type": "purchase",
                "company_id": self.company.id,
            }
        )
        self.sales_journal = self.env["account.journal"].create(
            {
                "name": "Sales Journal",
                "code": "SAL",
                "type": "sale",
                "company_id": self.company.id,
            }
        )

        self.company.iva_supplier_retention_journal_id = self.retention_journal.id
        self.company.iva_customer_retention_journal_id = self.retention_journal.id
        self.company.islr_supplier_retention_journal_id = self.retention_journal.id
        self.company.islr_customer_retention_journal_id = self.retention_journal.id

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "customer_rank": 1,
                "supplier_rank": 1,
            }
        )
        self.tax_iva_purchase = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        self.tax_iva_sale = self.env["account.tax"].create(
            {
                "name": "IVA 16% Sale",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )
        self.tax_islr_purchase = self.env["account.tax"].create(
            {
                "name": "ISLR 2%",
                "amount": 2,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        self.tax_islr_sale = self.env["account.tax"].create(
            {
                "name": "ISLR 2% Sale",
                "amount": 2,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "service",
                "list_price": 100,
            }
        )

    def _create_invoice(self, tax, move_type):
        journal = self.purchase_journal if move_type == "in_invoice" else self.sales_journal
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "journal_id": journal.id,
                "invoice_date": "2025-08-22",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [tax.id])],
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _create_retention(self, invoice, type_retention):
        today = fields.Date.today()
        payment_concept = self.env["payment.concept"].create({"name": "Test Payment Concept"})
        _logger.warning("Creating retention for invoice %s", invoice.amount_total)
        rate = 0.16 if type_retention == "iva" else 0.02
        return self.env["account.retention"].create(
            {
                "type_retention": type_retention,
                "type": invoice.move_type,
                "company_id": self.company.id,
                "partner_id": self.partner.id,
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
                                invoice.amount_untaxed * rate, precision_rounding=0.01
                            ),
                            "foreign_retention_amount": float_round(
                                invoice.amount_untaxed * rate, precision_rounding=0.01
                            ),
                            "foreign_invoice_amount": invoice.amount_untaxed,
                            "payment_concept_id": payment_concept.id,
                        }
                    )
                ],
            }
        )

    def test_create_supplier_iva_retention(self):
        invoice = self._create_invoice(self.tax_iva_purchase, "in_invoice")
        retention = self._create_retention(invoice, "iva")
        self.assertEqual(retention.type_retention, "iva")
        self.assertEqual(retention.type, "in_invoice")

    def test_create_customer_iva_retention(self):
        invoice = self._create_invoice(self.tax_iva_sale, "out_invoice")
        retention = self._create_retention(invoice, "iva")
        self.assertEqual(retention.type_retention, "iva")
        self.assertEqual(retention.type, "out_invoice")

    def test_create_supplier_islr_retention(self):
        invoice = self._create_invoice(self.tax_islr_purchase, "in_invoice")
        retention = self._create_retention(invoice, "islr")
        self.assertEqual(retention.type_retention, "islr")
        self.assertEqual(retention.type, "in_invoice")

    def test_create_customer_islr_retention(self):
        invoice = self._create_invoice(self.tax_islr_sale, "out_invoice")
        retention = self._create_retention(invoice, "islr")
        self.assertEqual(retention.type_retention, "islr")
        self.assertEqual(retention.type, "out_invoice")

    def test_sequence_created_on_create_iva(self):
        invoice = self._create_invoice(self.tax_iva_purchase, "in_invoice")
        retention = self._create_retention(invoice, "iva")
        retention.number = "0123456789"
        with self.assertRaises(ValidationError) as e:
            retention.action_post()
        self.assertIn(
            "IVA retention: Number must be exactly 14 numeric digits.",
            str(e.exception),
        )
