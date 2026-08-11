from odoo.tests import tagged
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "allowed_lines_move_ids")
class TestAllowedLinesMoveIds(RetentionTestCommon):
    """Regression tests for account.retention._compute_allowed_lines_move_ids.

    Before the fix, `retention.type == ["in_invoice", "in_refund", "in_debit"]`
    compared a Selection (a plain string) against a list, which is always
    False. As a result `allowed_types` always fell back to
    ("out_invoice", "out_refund"), regardless of the retention's actual type.

    The ISLR-availability filter uses `is_isrl_retention_available`
    (computed on account.move from whether any invoice line has a service
    product with a payment_concept), not `apply_islr_retention` — that other
    boolean exists on the model but is never exposed on any view, so it can
    never be True in practice and would make the domain permanently empty.
    `_create_invoice_islr` (product_islr_one, a service with a
    payment_concept) yields an ISLR-available invoice; `_create_invoice_reten_iva`
    (product_iva, a plain taxed product) does not.
    """

    def _post(self, invoice):
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def test_out_invoice_type_only_allows_sale_moves(self):
        out_inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="out_invoice", journal=self.sale_journal.id
        ))
        in_inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "partner_id": self.partner_pnr_75.id,
        })

        self.assertIn(out_inv, retention.allowed_lines_move_ids)
        self.assertNotIn(in_inv, retention.allowed_lines_move_ids)

    def test_in_invoice_type_only_allows_purchase_moves(self):
        # Regression: pre-fix, this used to incorrectly resolve to
        # ("out_invoice", "out_refund") and would return the sale move here.
        out_inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="out_invoice", journal=self.sale_journal.id
        ))
        in_inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "partner_id": self.partner_pnr_75.id,
        })

        self.assertIn(in_inv, retention.allowed_lines_move_ids)
        self.assertNotIn(out_inv, retention.allowed_lines_move_ids)

    def test_islr_retention_only_allows_moves_flagged_as_valid(self):
        valid_inv = self._post(self._create_invoice_islr(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))
        self.assertTrue(valid_inv.is_isrl_retention_available)

        not_valid_inv = self._post(self._create_invoice_reten_iva(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))
        self.assertFalse(not_valid_inv.is_isrl_retention_available)

        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "partner_id": self.partner_pnr_75.id,
        })

        self.assertIn(valid_inv, retention.allowed_lines_move_ids)
        self.assertNotIn(not_valid_inv, retention.allowed_lines_move_ids)

    def test_iva_retention_ignores_islr_availability(self):
        # For non-ISLR retentions, is_isrl_retention_available must not restrict the domain.
        inv = self._post(self._create_invoice_reten_iva(
            100, self.partner_pnr_75, out_invoice="in_invoice", journal=self.purchase_journal.id
        ))
        self.assertFalse(inv.is_isrl_retention_available)

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "partner_id": self.partner_pnr_75.id,
        })

        self.assertIn(inv, retention.allowed_lines_move_ids)
