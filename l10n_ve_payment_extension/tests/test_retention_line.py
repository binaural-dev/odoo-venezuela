# -*- coding: utf-8 -*-
# your_module/tests/test_retention_line.py

from odoo.tests import TransactionCase, tagged
from unittest.mock import patch

_logger = __import__('logging').getLogger(__name__)


@tagged('post_install', '-at_install', 'l10n_ve_retention_line')
class TestRetentionFlows(TransactionCase):
    """
    Pruebas unitarias para los flujos de cálculo de retenciones
    de ISLR y Municipal.
    """

    @classmethod
    def setUpClass(cls):
        """
        Configura los datos base que se compartirán entre todas las pruebas.
        Este método es "idempotente": se puede ejecutar varias veces sin fallar.
        """
        super(TestRetentionFlows, cls).setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.env.ref('base.VEF')
        cls.foreign_currency = cls.env.ref('base.USD')
        cls.company.write({
            "currency_id": cls.currency.id,
            "foreign_currency_id": cls.foreign_currency.id,
        })

        cls.partner = cls.env["res.partner"].search([('name', '=', 'Test Partner')], limit=1) or \
        cls.env["res.partner"].create({"name": "Test Partner"})
        
        cls.product = cls.env["product.product"].search([('name', '=', 'Test Service')], limit=1) or \
        cls.env["product.product"].create({"name": "Test Service", "type": "service"})

        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "purchase")], limit=1
        )
        
        cls.tax_unit = cls.env["tax.unit"].search([('name', '=', 'Test Tax Unit 2025')], limit=1) or \
        cls.env["tax.unit"].create({"name": "Test Tax Unit 2025", "value": 9.0, "status": True})

        cls.person_type = cls.env["type.person"].search([('name', '=', 'Test Person Type')], limit=1) or \
                          cls.env["type.person"].create({"name": "Test Person Type"})
        cls.partner.write({"type_person_id": cls.person_type.id})
        
        cls.islr_tariff = cls.env["fees.retention"].search([('name', '=', 'Test Tariff 3%')], limit=1) or \
                          cls.env["fees.retention"].create({"name": "Test Tariff 3%", "percentage": 3.0, "tax_unit_ids": cls.tax_unit.id})

        cls.payment_concept = cls.env["payment.concept"].search([('name', '=', 'Test ISLR Concept')], limit=1) or \
        cls.env["payment.concept"].create({
            "name": "Test ISLR Concept",
            "line_payment_concept_ids": [(0, 0, {
                "code": "ISLR-TEST-CODE", "type_person_id": cls.person_type.id,
                "percentage_tax_base": 100.0, "tariff_id": cls.islr_tariff.id,
            })],
        })

        country = cls.env['res.country'].search([('code', '=', 'TC')], limit=1) or \
                  cls.env['res.country'].create({'name': 'Test Country', 'code': 'TC'})
        
        state = cls.env['res.country.state'].search([('code', '=', 'TS'), ('country_id', '=', country.id)], limit=1) or \
                cls.env['res.country.state'].create({'name': 'Test State', 'code': 'TS', 'country_id': country.id})
        
        cls.municipality = cls.env['res.country.municipality'].search([('code', '=', 'MUN-TEST')], limit=1) or \
        cls.env['res.country.municipality'].create({
            'name': 'Test Municipality', 'code': 'MUN-TEST', 'country_id': country.id,
            'state_id': [(6, 0, [state.id])]
        })

        cls.branch = cls.env['economic.branch'].search([('name', '=', 'Test Branch')], limit=1) or \
        cls.env['economic.branch'].create({'name': 'Test Branch', 'status': 'active'})
        
        cls.economic_activity = cls.env['economic.activity'].search([('name', '=', 'Test Activity Code')], limit=1) or \
        cls.env['economic.activity'].create({
            'name': 'Test Activity Code', 'aliquot': 5.0, 'municipality_id': cls.municipality.id,
            'branch_id': cls.branch.id, 'description': 'Test Description',
            'minimum_monthly': 0, 'minimum_annual': 0,
        })

    def test_municipal_onchange_calculation(self):
        """Verifica que el onchange de la retención municipal calcula el monto correctamente."""
        invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "in_invoice",
            "journal_id": self.journal.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "quantity": 2, "price_unit": 100.0})],
        })
        invoice.flush_recordset()

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

    @patch("odoo.addons.l10n_ve_payment_extension.models.account_retention_line.AccountRetentionLine.onchange_economic_activity_id")
    def test_invoice_write_triggers_recalculation(self, mock_onchange_call):
        invoice = self.env["account.move"].create({"partner_id": self.partner.id, "move_type": "in_invoice", "journal_id": self.journal.id, "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "price_unit": 100.0})]})
        self.env['account.retention.line'].create({"name": "Initial Municipal Retention", "move_id": invoice.id, "economic_activity_id": self.economic_activity.id})
        invoice.flush_recordset()
        invoice.write({"invoice_line_ids": [(0, 0, {"product_id": self.product.id, "price_unit": 50.0})]})
        self.assertTrue(mock_onchange_call.called)

        _logger.info("========= test_invoice_write_triggers_recalculation passed =========")


    def test_islr_compute_fields(self):
        """
        Creates the line with dummy values !=0 to bypass the constraint while
        _compute_related_fields fills fields, then assigns payment_concept_id.
        """
        foreign = self.env.ref("base.USD", raise_if_not_found=False) \
            or self.env["res.currency"].search([("name", "=", "USD")], limit=1) \
            or self.env["res.currency"].create({"name": "USD", "symbol": "$", "rounding": 0.01, "position": "before"})

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

        if "foreign_amount_untaxed" in (invoice.tax_totals or {}):
            self.assertAlmostEqual(line.foreign_invoice_amount, 500.0, places=2)

    def _ensure_tax_totals(self, move):
        """
        Gets/updates tax_totals in a way compatible across Odoo versions.
        Returns the tax_totals dict.
        """
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
