# -*- coding: utf-8 -*-
"""
Tests for helpdesk #14548: prevent duplicated invoice/document numbers on the
lines of a customer (client) IVA/ISLR retention, which used to let the user
inflate the retained amount by repeating the same invoice.
"""
from odoo.tests import tagged, Form
from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_round
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_duplicate_lines")
class TestRetentionDuplicateLines(RetentionTestCommon):

    def setUp(self):
        super().setUp()
        # Extra 8% IVA tax/product so we can build a legitimate case where the
        # same invoice has two different real tax rates.
        self.tax_iva_8 = self.env["account.tax"].create({
            "name": "IVA 8% Ventas",
            "amount_type": "percent",
            "amount": 8.0,
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group_iva.id,
            "country_id": self.company.country_id.id,
        })
        self.tax_iva_8_purchase = self.env["account.tax"].create({
            "name": "IVA 8% Compras",
            "amount_type": "percent",
            "amount": 8.0,
            "type_tax_use": "purchase",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group_iva.id,
            "country_id": self.company.country_id.id,
        })
        self.product_iva_8 = self.env["product.product"].create({
            "name": "Servicio 8%",
            "list_price": 100,
            "property_account_income_id": self.acc_income.id,
            "taxes_id": [(6, 0, [self.tax_iva_8.id])],
            "supplier_taxes_id": [(6, 0, [self.tax_iva_8_purchase.id])],
        })

    def _create_out_invoice_with_lines(self, product_lines):
        """product_lines: list of (product, price_unit) tuples."""
        with Form(
            self.env["account.move"].with_context(
                default_move_type="out_invoice", default_journal_id=self.sale_journal.id
            )
        ) as inv_form:
            inv_form.partner_id = self.partner_pnr_75
            inv_form.invoice_date = fields.Date.today()
            inv_form.currency_id = self.currency_vef

        inv = inv_form.save()
        with Form(inv) as inv_form_edit:
            for product, price_unit in product_lines:
                with inv_form_edit.invoice_line_ids.new() as line:
                    line.product_id = product
                    line.quantity = 1
                    line.price_unit = price_unit
        inv = inv_form_edit.save()
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        inv.action_post()
        return inv

    def _make_iva_customer_retention(self, invoice, lines_vals):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "number": "01234567891234",
            "retention_line_ids": [Command.create(vals) for vals in lines_vals],
        })

    def _make_islr_customer_retention(self, invoice, lines_vals):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "number": "01234567891234",
            "retention_line_ids": [Command.create(vals) for vals in lines_vals],
        })

    def test_iva_duplicate_same_tax_raises(self):
        """Same invoice repeated at the same real tax rate must be rejected."""
        invoice = self._create_out_invoice_with_lines([(self.product_iva, 100.0)])

        line_vals = {
            "move_id": invoice.id,
            "name": "Iva Retention",
            "invoice_type": "out_invoice",
            "aliquot": 16.0,
            "iva_amount": 16.0,
            "invoice_total": invoice.amount_total,
            "invoice_amount": invoice.amount_untaxed,
            "retention_amount": float_round(invoice.amount_untaxed * 0.75 * 0.16, precision_rounding=0.01),
            "foreign_invoice_amount": invoice.amount_untaxed,
            "foreign_retention_amount": float_round(invoice.amount_untaxed * 0.75 * 0.16, precision_rounding=0.01),
            "foreign_currency_rate": 1.0,
        }
        retention = self._make_iva_customer_retention(
            invoice, [line_vals, dict(line_vals)]
        )

        with self.assertRaises(ValidationError) as e:
            retention.action_post()
        self.assertIn("duplicated", str(e.exception))

        _logger.info("========= test_iva_duplicate_same_tax_raises passed =========")

    def test_iva_distinct_tax_rates_allowed(self):
        """Same invoice with two different real tax rates is legitimate."""
        invoice = self._create_out_invoice_with_lines(
            [(self.product_iva, 100.0), (self.product_iva_8, 100.0)]
        )

        line_16 = {
            "move_id": invoice.id,
            "name": "Iva Retention 16",
            "invoice_type": "out_invoice",
            "aliquot": 16.0,
            "iva_amount": 16.0,
            "invoice_total": invoice.amount_total,
            "invoice_amount": 100.0,
            "retention_amount": 12.0,
            "foreign_invoice_amount": 100.0,
            "foreign_retention_amount": 12.0,
            "foreign_currency_rate": 1.0,
        }
        line_8 = {
            "move_id": invoice.id,
            "name": "Iva Retention 8",
            "invoice_type": "out_invoice",
            "aliquot": 8.0,
            "iva_amount": 8.0,
            "invoice_total": invoice.amount_total,
            "invoice_amount": 100.0,
            "retention_amount": 6.0,
            "foreign_invoice_amount": 100.0,
            "foreign_retention_amount": 6.0,
            "foreign_currency_rate": 1.0,
        }
        retention = self._make_iva_customer_retention(invoice, [line_16, line_8])

        retention.action_post()
        self.assertEqual(retention.state, "emitted")

        _logger.info("========= test_iva_distinct_tax_rates_allowed passed =========")

    def test_islr_duplicate_same_concept_raises(self):
        """Same invoice repeated for the same payment concept must be rejected."""
        invoice = self._create_out_invoice_with_lines([(self.product_islr_one, 500.0)])

        line_vals = {
            "move_id": invoice.id,
            "name": "ISLR Retention",
            "invoice_type": "out_invoice",
            "payment_concept_id": self.concept_one.id,
            "invoice_total": invoice.amount_total,
            "invoice_amount": invoice.amount_untaxed,
            "retention_amount": float_round(invoice.amount_untaxed * 0.03, precision_rounding=0.01),
            "foreign_invoice_amount": invoice.amount_untaxed,
            "foreign_retention_amount": float_round(invoice.amount_untaxed * 0.03, precision_rounding=0.01),
        }
        retention = self._make_islr_customer_retention(
            invoice, [line_vals, dict(line_vals)]
        )

        with self.assertRaises(ValidationError) as e:
            retention.action_post()
        self.assertIn("duplicated", str(e.exception))

        _logger.info("========= test_islr_duplicate_same_concept_raises passed =========")

    def test_islr_distinct_concept_allowed(self):
        """Same invoice with two different payment concepts is legitimate."""
        invoice = self._create_out_invoice_with_lines(
            [(self.product_islr_one, 500.0), (self.product_islr_three, 300.0)]
        )

        line_concept_one = {
            "move_id": invoice.id,
            "name": "ISLR Retention Concept One",
            "invoice_type": "out_invoice",
            "payment_concept_id": self.concept_one.id,
            "invoice_total": invoice.amount_total,
            "invoice_amount": 500.0,
            "retention_amount": 15.0,
            "foreign_invoice_amount": 500.0,
            "foreign_retention_amount": 15.0,
        }
        line_concept_three = {
            "move_id": invoice.id,
            "name": "ISLR Retention Concept Three",
            "invoice_type": "out_invoice",
            "payment_concept_id": self.concept_three.id,
            "invoice_total": invoice.amount_total,
            "invoice_amount": 300.0,
            "retention_amount": 9.0,
            "foreign_invoice_amount": 300.0,
            "foreign_retention_amount": 9.0,
        }
        retention = self._make_islr_customer_retention(
            invoice, [line_concept_one, line_concept_three]
        )

        retention.action_post()
        self.assertEqual(retention.state, "emitted")

        _logger.info("========= test_islr_distinct_concept_allowed passed =========")

    def test_supplier_retention_not_affected_by_duplicate_check(self):
        """Supplier (in_invoice) retentions must not be touched by this check,
        even if lines happen to repeat move_id/aliquot."""
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()

        line_vals = {
            "move_id": invoice.id,
            "name": "IVA Retention",
            "invoice_total": invoice.amount_total,
            "invoice_amount": invoice.amount_untaxed,
            "aliquot": 16.0,
            "retention_amount": float_round(invoice.amount_untaxed * 0.16, precision_rounding=0.01),
            "foreign_currency_rate": 1.0,
            "foreign_invoice_amount": invoice.amount_untaxed,
            "foreign_retention_amount": float_round(invoice.amount_untaxed * 0.16, precision_rounding=0.01),
        }
        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [
                Command.create(line_vals), Command.create(dict(line_vals))
            ],
        })

        # Should not raise from the new duplicate-lines check (it may still
        # raise from unrelated business validations, but never with the
        # "duplicated" wording introduced by this fix).
        try:
            retention.action_post()
        except ValidationError as e:
            self.assertNotIn("duplicated", str(e.exception))

        _logger.info(
            "========= test_supplier_retention_not_affected_by_duplicate_check passed ========="
        )
