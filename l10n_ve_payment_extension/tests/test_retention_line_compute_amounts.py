from odoo.tests import tagged
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_line_compute_amounts")
class TestRetentionLineComputeAmounts(RetentionTestCommon):
    """Regression tests for account.retention.line._compute_amounts.

    Before the fix, when the company currency was not VEF, this compute
    recalculated `invoice_amount` as `foreign_invoice_amount * (1 /
    foreign_currency_rate)`. If `foreign_currency_rate` was 0 (a real path:
    `_compute_related_fields` sets it to 0.0 when no accumulated-rate tariff
    tier matches), this raised a ZeroDivisionError. It also duplicated logic
    that should simply read `move_id.tax_totals["base_amount"]`, the same
    source used everywhere else in this file for `invoice_amount`.
    """

    def setUp(self):
        super().setUp()
        self.usd_company = self.env["res.company"].create({
            "name": "USD Co (non VEF base)",
            "currency_id": self.currency_usd.id,
        })

    def test_does_not_divide_by_zero_when_rate_is_zero(self):
        inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))
        line = self.env["account.retention.line"].create({
            "move_id": inv.id,
            "company_id": self.company.id,
        })
        line.write({
            "invoice_amount": 100.0,
            "foreign_invoice_amount": 50.0,
            "foreign_currency_rate": 0.0,
        })

        line.with_company(self.usd_company)._compute_amounts()

    def test_uses_tax_totals_base_amount_when_company_currency_is_not_vef(self):
        inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))
        line = self.env["account.retention.line"].create({
            "move_id": inv.id,
            "company_id": self.company.id,
        })
        line.write({
            "invoice_amount": 100.0,
            "foreign_invoice_amount": 50.0,
            "foreign_currency_rate": 390.2944,
        })

        line.with_company(self.usd_company)._compute_amounts()

        self.assertEqual(line.invoice_amount, inv.tax_totals["base_amount"])

    def test_does_not_recompute_when_company_currency_is_vef(self):
        inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))
        line = self.env["account.retention.line"].create({
            "move_id": inv.id,
            "company_id": self.company.id,
        })
        line.write({
            "invoice_amount": 123.45,
            "foreign_invoice_amount": 50.0,
            "foreign_currency_rate": 0.0,
        })

        # Company currency is VEF (the default in RetentionTestCommon), so the
        # branch that reads tax_totals must not run and invoice_amount stays untouched.
        line._compute_amounts()

        self.assertEqual(line.invoice_amount, 123.45)

    def _post(self, invoice):
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice
