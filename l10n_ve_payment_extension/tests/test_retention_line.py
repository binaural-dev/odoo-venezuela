# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo import Command, fields
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_retention_line")
class TestRetentionFlows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestRetentionFlows, cls).setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.env.ref("base.VEF")
        cls.foreign_currency = cls.env.ref("base.USD")
        cls.company.write({
            "currency_id": cls.currency.id,
            "foreign_currency_id": cls.foreign_currency.id,
        })
        cls.partner = cls.env["res.partner"].search([("name", "=", "Test Partner")], limit=1) or             cls.env["res.partner"].create({"name": "Test Partner"})
        cls.product = cls.env["product.product"].search([("name", "=", "Test Service")], limit=1) or             cls.env["product.product"].create({"name": "Test Service", "type": "service"})
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "purchase")], limit=1
        )
        cls.tax_unit = cls.env["tax.unit"].search([("name", "=", "Test Tax Unit 2025")], limit=1) or             cls.env["tax.unit"].create({"name": "Test Tax Unit 2025", "value": 9.0, "status": True})
        cls.person_type = cls.env["type.person"].search([("name", "=", "Test Person Type")], limit=1) or             cls.env["type.person"].create({"name": "Test Person Type"})
        cls.partner.write({"type_person_id": cls.person_type.id})
        cls.islr_tariff = cls.env["fees.retention"].search([("name", "=", "Test Tariff 3%")], limit=1) or             cls.env["fees.retention"].create({"name": "Test Tariff 3%", "percentage": 3.0, "tax_unit_ids": cls.tax_unit.id})
        cls.payment_concept = cls.env["payment.concept"].search([("name", "=", "Test ISLR Concept")], limit=1) or             cls.env["payment.concept"].create({
                "name": "Test ISLR Concept",
                "line_payment_concept_ids": [(0, 0, {
                    "code": "ISLR-TEST-CODE", "type_person_id": cls.person_type.id,
                    "percentage_tax_base": 100.0, "tariff_id": cls.islr_tariff.id,
                })],
            })
        country = cls.env["res.country"].search([("code", "=", "TC")], limit=1) or             cls.env["res.country"].create({"name": "Test Country", "code": "TC"})
        state = cls.env["res.country.state"].search([("code", "=", "TS")], limit=1) or             cls.env["res.country.state"].create({"name": "Test State", "code": "TS", "country_id": country.id})
        cls.municipality = cls.env["res.country.municipality"].search([("code", "=", "MUN-TEST")], limit=1) or             cls.env["res.country.municipality"].create({
                "name": "Test Municipality", "code": "MUN-TEST",
                "country_id": country.id, "state_id": [(6, 0, [state.id])]
            })
        cls.branch = cls.env["economic.branch"].search([("name", "=", "Test Branch")], limit=1) or             cls.env["economic.branch"].create({"name": "Test Branch", "status": "active"})
        cls.economic_activity = cls.env["economic.activity"].search([("name", "=", "Test Activity Code")], limit=1) or             cls.env["economic.activity"].create({
                "name": "Test Activity Code", "aliquot": 5.0,
                "municipality_id": cls.municipality.id, "branch_id": cls.branch.id,
                "description": "Test Description", "minimum_monthly": 0, "minimum_annual": 0,
            })

    def test_municipal_onchange_calculation(self):
        invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "in_invoice",
            "journal_id": self.journal.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "quantity": 2, "price_unit": 100.0})],
        })
        retention_line = self.env["account.retention.line"].new({
            "move_id": invoice.id,
            "aliquot": self.economic_activity.aliquot,
            "economic_activity_id": self.economic_activity.id,
        })
        retention_line.onchange_economic_activity_id()
        retention_line.onchange_municipal_invoice_amount()
        expected_retention = 200.0 * 0.05
        self.assertAlmostEqual(retention_line.retention_amount, expected_retention, places=2)
        _logger.info("========= test_municipal_onchange_calculation passed =========")

    def test_invoice_write_triggers_recalculation(self):
        invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "in_invoice",
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "price_unit": 100.0})],
        })
        retention = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [
                Command.create({
                    "move_id": invoice.id,
                    "economic_activity_id": self.economic_activity.id,
                    "invoice_total": 200.0,
                    "invoice_amount": 200.0,
                    "retention_amount": 10.0,
                    "foreign_invoice_amount": 200.0,
                    "foreign_retention_amount": 10.0,
                })
            ],
        })
        line = invoice.retention_municipal_line_ids[0]
        invoice.write({
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "price_unit": 50.0})],
        })
        self.assertEqual(line.economic_activity_id, self.economic_activity)
        self.assertAlmostEqual(line.aliquot, self.economic_activity.aliquot, places=2)
        _logger.info("========= test_invoice_write_triggers_recalculation passed =========")

    def test_islr_compute_fields(self):
        foreign = self.env.ref("base.USD", raise_if_not_found=False) or             self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "in_invoice",
            "journal_id": self.journal.id,
            "currency_id": foreign.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "price_unit": 500.0})],
        })
        for k in ("foreign_rate", "foreign_inverse_rate"):
            if k in invoice._fields:
                invoice.write({k: 1.0})
        self._ensure_tax_totals(invoice)
        line = self.env["account.retention.line"].create({
            "name": "Test ISLR Line (temp)",
            "move_id": invoice.id,
            "invoice_total": 1.0,
            "invoice_amount": 1.0,
            "retention_amount": 1.0,
            "foreign_invoice_amount": 1.0,
            "foreign_retention_amount": 1.0,
        })
        line.write({"payment_concept_id": self.payment_concept.id})
        self._ensure_tax_totals(invoice)
        line.invalidate_recordset()
        self.assertAlmostEqual(line.related_percentage_fees, 3.0, places=2)
        self.assertAlmostEqual(line.invoice_amount, 500.0, places=2)
        if "base_amount_foreign_currency" in (invoice.tax_totals or {}):
            self.assertAlmostEqual(line.foreign_invoice_amount, 500.0, places=2)
        _logger.info("========= test_islr_compute_fields passed =========")

    def _ensure_tax_totals(self, move):
        for name in ("_compute_tax_totals_json", "_recompute_tax_lines", "_onchange_invoice_line_ids"):
            func = getattr(move, name, None)
            if callable(func):
                func()
                break
        _ = move.tax_totals
        if hasattr(move, "flush_recordset") and callable(move.flush_recordset):
            move.flush_recordset()
        elif hasattr(move, "invalidate_recordset") and callable(move.invalidate_recordset):
            move.invalidate_recordset()
        return move.tax_totals
