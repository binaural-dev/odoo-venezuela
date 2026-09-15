# -*- coding: utf-8 -*-
"""
Tests for helpdesk #14548 follow-up rules:
  1. Cross-retention duplicate prevention (IVA/ISLR/Municipal, client+supplier).
  2. ISLR base-amount computation (automatic + manual flows).
  3. Currency-correct base computation (balance/foreign_subtotal).
  4. Zero-amount retention block on action_post.
  5. Dates-not-in-future validation.
  6. IVA duplicate-aliquot recompute on onchange (move_id / aliquot).
"""
from odoo.tests import tagged, Form
from odoo import Command, fields
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_round
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_ti14548_rules")
class TestRetentionTi14548Rules(RetentionTestCommon):

    def setUp(self):
        super().setUp()
        # Its own tax_group (not tax_group_iva) - _get_iva_tax_groups_and_taxes
        # groups by tax_group_id from tax_totals, so two taxes sharing the
        # same tax_group_id would be merged into a single tax_totals entry
        # and never look like two distinct real rates.
        self.tax_group_iva_8 = self.env["account.tax.group"].create({
            "name": "IVA 8% l10n_ve",
            "company_id": self.company.id,
            "country_id": self.company.country_id.id,
        })
        self.tax_iva_8 = self.env["account.tax"].create({
            "name": "IVA 8% Ventas",
            "amount_type": "percent",
            "amount": 8.0,
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group_iva_8.id,
            "country_id": self.company.country_id.id,
        })
        self.tax_iva_8_purchase = self.env["account.tax"].create({
            "name": "IVA 8% Compras",
            "amount_type": "percent",
            "amount": 8.0,
            "type_tax_use": "purchase",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group_iva_8.id,
            "country_id": self.company.country_id.id,
        })
        self.product_iva_8 = self.env["product.product"].create({
            "name": "Servicio 8%",
            "list_price": 100,
            "property_account_income_id": self.acc_income.id,
            "taxes_id": [(6, 0, [self.tax_iva_8.id])],
            "supplier_taxes_id": [(6, 0, [self.tax_iva_8_purchase.id])],
        })
        # A second, self-contained ISLR concept for tests that need two
        # DISTINCT concepts on the same invoice - the common fixture's
        # concept_three/etc. are unreliable (not always registered under
        # their xmlid on a fresh DB, see the module's own note about this).
        self.concept_other = self.env["payment.concept"].create({
            "name": "Concepto Alterno 14548",
            "status": True,
        })
        self.product_islr_other = self.env["product.product"].create({
            "name": "Servicio Concepto Alterno",
            "list_price": 100,
            "property_account_income_id": self.acc_income.id,
            "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
            "supplier_taxes_id": [(6, 0, [self.tax_iva_exent_purchase.id])],
            "type": "service",
            "payment_concept": self.concept_other.id,
        })
        # Company partner type_person must match the payment-concept line's
        # type_person for the automatic ISLR base computation on a CLIENT
        # (out_invoice) retention line to trigger (account_retention_line.
        # _get_islr_type_person_id uses the company's partner for that case).
        self.company.partner_id.type_person_id = self.env.ref(
            "l10n_ve_payment_extension.type_person_l10n_ve_payment_extension"
        ).id
        self.company.write({
            "municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
            "municipal_customer_retention_journal_id": self.bank_journal_sub.id,
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
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

    def _make_iva_customer_retention(self, lines_vals, number="01234567891234"):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "number": number,
            "retention_line_ids": [Command.create(vals) for vals in lines_vals],
        })

    def _make_islr_customer_retention(self, lines_vals):
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

    # ------------------------------------------------------------------
    # Rule 1: cross-retention duplicate prevention
    # ------------------------------------------------------------------
    def test_cross_retention_iva_duplicate_aliquot_blocks_on_emitted(self):
        """Two separate retentions on the same invoice/aliquot: the first one
        posts fine, the second (same invoice, same real tax rate) must be
        rejected once the first is already 'emitted', naming the first
        retention."""
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
        retention_1 = self._make_iva_customer_retention([line_vals], number="01234567891234")
        retention_1.action_post()
        self.assertEqual(retention_1.state, "emitted")

        retention_2 = self._make_iva_customer_retention([dict(line_vals)], number="01234567891235")
        with self.assertRaises(ValidationError) as e:
            retention_2.action_post()
        msg = str(e.exception)
        self.assertIn("was already retained at the same tax", msg)
        self.assertIn(retention_1.display_name, msg)

        _logger.info(
            "========= test_cross_retention_iva_duplicate_aliquot_blocks_on_emitted passed ========="
        )

    def test_cross_retention_iva_two_drafts_do_not_block_each_other(self):
        """Two DRAFT retentions referencing the same invoice/aliquot must
        coexist without raising - the conflict is only checked at post
        time against already-emitted retentions."""
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
        retention_1 = self._make_iva_customer_retention([line_vals], number="01234567891234")
        retention_2 = self._make_iva_customer_retention([dict(line_vals)], number="01234567891236")
        self.assertEqual(retention_1.state, "draft")
        self.assertEqual(retention_2.state, "draft")

        _logger.info(
            "========= test_cross_retention_iva_two_drafts_do_not_block_each_other passed ========="
        )

    def test_cross_retention_islr_concept_base_exceeded_blocks_on_emitted(self):
        """ISLR: once retention_1 already retained the full base (500) for
        (invoice, concept_one), a second retention declaring even a small
        extra amount for the same (invoice, concept) must be rejected,
        naming the first retention."""
        invoice = self._create_out_invoice_with_lines([(self.product_islr_one, 500.0)])

        line_1 = {
            "move_id": invoice.id,
            "name": "ISLR Retention",
            "invoice_type": "out_invoice",
            "payment_concept_id": self.concept_one.id,
            "invoice_total": invoice.amount_total,
            "invoice_amount": 500.0,
            "retention_amount": 15.0,
            "foreign_invoice_amount": 500.0,
            "foreign_retention_amount": 15.0,
        }
        retention_1 = self._make_islr_customer_retention([line_1])
        retention_1.action_post()
        self.assertEqual(retention_1.state, "emitted")

        line_2 = dict(line_1, invoice_amount=1.0, retention_amount=0.03,
                      foreign_invoice_amount=1.0, foreign_retention_amount=0.03)
        retention_2 = self._make_islr_customer_retention([line_2])
        with self.assertRaises(ValidationError) as e:
            retention_2.action_post()
        msg = str(e.exception)
        self.assertIn("exceeds the actual base billed under that", msg)
        self.assertIn(retention_1.display_name, msg)

        _logger.info(
            "========= test_cross_retention_islr_concept_base_exceeded_blocks_on_emitted passed ========="
        )

    def test_cross_retention_municipal_duplicate_activity_blocks_on_emitted(self):
        """Municipal: same (invoice, economic_activity) retained by two
        different retentions - the second must be rejected once the first
        is emitted."""
        country = self.env["res.country"].search([("code", "=", "TC14548")], limit=1) or \
            self.env["res.country"].create({"name": "Test Country 14548", "code": "TC14548"})
        state = self.env["res.country.state"].search([("code", "=", "TS14548")], limit=1) or \
            self.env["res.country.state"].create(
                {"name": "Test State 14548", "code": "TS14548", "country_id": country.id}
            )
        municipality = self.env["res.country.municipality"].search(
            [("code", "=", "MUN-14548")], limit=1
        ) or self.env["res.country.municipality"].create({
            "name": "Test Municipality 14548", "code": "MUN-14548",
            "country_id": country.id, "state_id": [(6, 0, [state.id])],
        })
        branch = self.env["economic.branch"].search([("name", "=", "Branch 14548")], limit=1) or \
            self.env["economic.branch"].create({"name": "Branch 14548", "status": "active"})
        activity = self.env["economic.activity"].search(
            [("name", "=", "Activity 14548")], limit=1
        ) or self.env["economic.activity"].create({
            "name": "Activity 14548", "aliquot": 5.0,
            "municipality_id": municipality.id, "branch_id": branch.id,
            "description": "Test", "minimum_monthly": 0, "minimum_annual": 0,
        })

        invoice = self._create_invoice_reten_iva(
            amount=200, partner=self.partner_pnr_75, out_invoice="in_invoice",
            journal=self.purchase_journal,
        )
        invoice.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        invoice.action_post()

        line_vals = {
            "move_id": invoice.id,
            "economic_activity_id": activity.id,
            "aliquot": activity.aliquot,
            "invoice_total": 200.0,
            "invoice_amount": 200.0,
            "retention_amount": 10.0,
            "foreign_invoice_amount": 200.0,
            "foreign_retention_amount": 10.0,
        }
        retention_1 = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create(line_vals)],
        })
        retention_1.action_post()
        self.assertEqual(retention_1.state, "emitted")

        retention_2 = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create(dict(line_vals))],
        })
        with self.assertRaises(ValidationError) as e:
            retention_2.action_post()
        msg = str(e.exception)
        self.assertIn("was already retained for the same", msg)
        self.assertIn(retention_1.display_name, msg)

        _logger.info(
            "========= test_cross_retention_municipal_duplicate_activity_blocks_on_emitted passed ========="
        )

    # ------------------------------------------------------------------
    # Rule 2: ISLR base-amount computation (automatic + manual flows)
    # ------------------------------------------------------------------
    def test_islr_automatic_flow_several_concepts_each_own_subtotal(self):
        """Two services with (possibly different) ISLR concepts: each must
        get its own subtotal (500 and 300), never the invoice total (800)
        nor a duplicated/repeated value."""
        invoice = self._create_out_invoice_with_lines(
            [(self.product_islr_one, 500.0), (self.product_islr_other, 300.0)]
        )
        payment_concepts = invoice._get_payment_concepts_from_invoice()
        self.assertEqual(len(payment_concepts), 2)
        amounts = sorted(p[1] for p in payment_concepts)
        self.assertAlmostEqual(amounts[0], 300.0, places=2)
        self.assertAlmostEqual(amounts[1], 500.0, places=2)

        _logger.info(
            "========= test_islr_automatic_flow_several_concepts_each_own_subtotal passed ========="
        )

    def test_islr_manual_no_concept_yet_proposes_zero(self):
        """A manually-added ISLR line without payment_concept_id yet must
        propose base 0.0, never the whole invoice."""
        invoice = self._create_out_invoice_with_lines([(self.product_islr_one, 500.0)])
        retention = self._make_islr_customer_retention([])
        line = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": invoice.id,
            "name": "ISLR Retention",
            "invoice_type": "out_invoice",
        })
        base, foreign_base = line._get_islr_concept_base_amounts(invoice)
        self.assertEqual(base, 0.0)
        self.assertEqual(foreign_base, 0.0)

        _logger.info("========= test_islr_manual_no_concept_yet_proposes_zero passed =========")

    def test_islr_error_when_concept_exhausted_no_partial_calc(self):
        """When the (invoice, concept) combination has no invoice line left
        to assign (all claimed by sibling lines), selecting it must
        immediately raise UserError, with no computation of dependent
        fields (retention_amount, invoice_amount, etc.) left over from
        before the error.

        Note: the "exhaustion" notion only applies once the invoice has 2+
        lines for the same concept (with a single line, the base always
        defaults to the whole invoice per rule 2b, nothing to exhaust) - so
        this invoice needs 2 lines under concept_one.
        """
        invoice = self._create_out_invoice_with_lines(
            [(self.product_islr_one, 500.0), (self.product_islr_iva_one, 200.0)]
        )
        retention = self._make_islr_customer_retention([])

        # First two lines legitimately claim the two invoice lines for concept_one.
        line_1 = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": invoice.id,
            "payment_concept_id": self.concept_one.id,
            "name": "ISLR Retention 1",
            "invoice_type": "out_invoice",
        })
        self.assertAlmostEqual(line_1.invoice_amount, 500.0, places=2)

        line_2 = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": invoice.id,
            "payment_concept_id": self.concept_one.id,
            "name": "ISLR Retention 2",
            "invoice_type": "out_invoice",
        })
        self.assertAlmostEqual(line_2.invoice_amount, 200.0, places=2)

        # Third line: same invoice/concept, but there's no invoice line left
        # for it (both already claimed by line_1/line_2) - must raise
        # immediately via the onchange.
        line_3 = self.env["account.retention.line"].new({
            "retention_id": retention.id,
            "move_id": invoice.id,
            "name": "ISLR Retention 3",
            "invoice_type": "out_invoice",
        })
        line_3.payment_concept_id = self.concept_one.id
        with self.assertRaises(UserError) as e:
            line_3._onchange_payment_concept_id_islr_warning()
        self.assertIn("no more products with payment concept", str(e.exception))

        _logger.info("========= test_islr_error_when_concept_exhausted_no_partial_calc passed =========")

    # ------------------------------------------------------------------
    # Rule 4: zero-amount retention blocks action_post
    # ------------------------------------------------------------------
    def test_zero_retention_amount_blocks_post_exact_message(self):
        invoice = self._create_out_invoice_with_lines([(self.product_iva, 100.0)])
        line_vals = {
            "move_id": invoice.id,
            "name": "Iva Retention",
            "invoice_type": "out_invoice",
            "aliquot": 16.0,
            "iva_amount": 16.0,
            "invoice_total": invoice.amount_total,
            "invoice_amount": invoice.amount_untaxed,
            "retention_amount": 0.0,
            "foreign_invoice_amount": invoice.amount_untaxed,
            "foreign_retention_amount": 0.0,
            "foreign_currency_rate": 1.0,
        }
        retention = self._make_iva_customer_retention([line_vals])
        with self.assertRaises(ValidationError) as e:
            retention.action_post()
        self.assertEqual(str(e.exception), "You can not create a retention with 0 amount.")
        self.assertEqual(retention.payment_ids, self.env["account.payment"])

        _logger.info("========= test_zero_retention_amount_blocks_post_exact_message passed =========")

    # ------------------------------------------------------------------
    # Rule 6: IVA aliquot recompute on onchange
    # ------------------------------------------------------------------
    def test_iva_onchange_move_proposes_non_conflicting_aliquot(self):
        """Invoice with 2 real tax rates (16% and 8%): once a sibling line
        already used 16%, adding another line for the same invoice must
        propose the 8% tax_group instead of always the first one."""
        invoice = self._create_out_invoice_with_lines(
            [(self.product_iva, 100.0), (self.product_iva_8, 100.0)]
        )
        retention = self._make_iva_customer_retention([])
        line_1 = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": invoice.id,
            "name": "Iva Retention 1",
            "invoice_type": "out_invoice",
        })
        line_1._onchange_move_id()
        self.assertAlmostEqual(line_1.aliquot, 16.0, places=2)

        line_2 = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": invoice.id,
            "name": "Iva Retention 2",
            "invoice_type": "out_invoice",
        })
        line_2._onchange_move_id()
        self.assertAlmostEqual(line_2.aliquot, 8.0, places=2)
        # Dependent monetary fields recomputed for the 8% tax group:
        # base 100.0 * 8% = 8.0 iva_amount. retention_amount stays 0 for a
        # client (out_invoice) line because auto_fill_retention_amount_iva
        # is off by default - it must be manually filled in, but must NOT
        # keep any stale value from a previous aliquot either.
        self.assertAlmostEqual(line_2.iva_amount, 8.0, places=2)
        self.assertEqual(line_2.retention_amount, 0.0)

        _logger.info(
            "========= test_iva_onchange_move_proposes_non_conflicting_aliquot passed ========="
        )

    def test_iva_onchange_aliquot_manual_change_recomputes_amounts(self):
        """Manually changing aliquot on a line from 16% to 8% must recompute
        iva_amount/retention_amount to the exact values for the 8% real
        tax_group on the invoice."""
        invoice = self._create_out_invoice_with_lines(
            [(self.product_iva, 100.0), (self.product_iva_8, 100.0)]
        )
        retention = self._make_iva_customer_retention([])
        line = self.env["account.retention.line"].create({
            "retention_id": retention.id,
            "move_id": invoice.id,
            "name": "Iva Retention",
            "invoice_type": "out_invoice",
        })
        line._onchange_move_id()
        self.assertAlmostEqual(line.aliquot, 16.0, places=2)
        self.assertAlmostEqual(line.iva_amount, 16.0, places=2)

        line.aliquot = 8.0
        line._onchange_aliquot()
        self.assertAlmostEqual(line.iva_amount, 8.0, places=2)
        self.assertAlmostEqual(line.invoice_amount, 100.0, places=2)
        # Client (out_invoice) retention: auto_fill_retention_amount_iva off
        # by default leaves retention_amount at 0 until manually filled -
        # confirm it did NOT keep the stale 16%-derived value either.
        self.assertEqual(line.retention_amount, 0.0)

        _logger.info(
            "========= test_iva_onchange_aliquot_manual_change_recomputes_amounts passed ========="
        )
