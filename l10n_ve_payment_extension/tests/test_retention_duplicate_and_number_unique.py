import logging

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_duplicate_and_number_unique")
class TestRetentionDuplicateAndNumberUnique(RetentionTestCommon):
    """Regression tests for duplicating a retention from the list view and
    for the uniqueness of the voucher `number`.

    Before the fix, `account.retention` had no `copy=False` on `number`,
    `state`, `retention_line_ids` or `payment_ids`: duplicating an emitted
    retention produced another "emitted" retention with the *same* voucher
    number, still pointing at the original invoices. There was also no
    constraint stopping two retentions of the same company/type from
    sharing a manually-typed number.
    """

    def _create_islr_retention_with_line(self, number=None):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        self._prepare_invoice_for_retention(inv)
        inv.action_post()

        vals = {
            "type_retention": "islr", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "retention_line_ids": [Command.create({
                "move_id": inv.id, "payment_concept_id": self.concept_one.id,
                "invoice_type": "in_invoice", "name": "Test",
                "invoice_amount": 500.0, "invoice_total": 500.0,
                "retention_amount": 15.0,
            })],
        }
        if number:
            vals["number"] = number
        return self.env["account.retention"].create(vals)

    def test_duplicate_resets_number_state_and_lines(self):
        retention = self._create_islr_retention_with_line()
        retention.state = "emitted"
        self.assertTrue(retention.number)

        duplicate = retention.copy()

        self.assertEqual(duplicate.state, "draft")
        self.assertTrue(duplicate.number)
        self.assertNotEqual(duplicate.number, retention.number)
        self.assertFalse(duplicate.retention_line_ids)
        self.assertFalse(duplicate.payment_ids)
        _logger.info("========= test_duplicate_resets_number_state_and_lines passed =========")

    def test_duplicate_number_same_type_retention_raises(self):
        self._create_islr_retention_with_line(number="ISLR-DUP-TEST")

        with self.assertRaises(ValidationError):
            self._create_islr_retention_with_line(number="ISLR-DUP-TEST")
        _logger.info("========= test_duplicate_number_same_type_retention_raises passed =========")

    def test_same_number_different_type_retention_allowed(self):
        # IVA and ISLR use independent sequences/books, so the same voucher
        # number is not a real collision across type_retention values.
        islr_retention = self._create_islr_retention_with_line(number="SHARED-NUMBER")

        iva_retention = self.env["account.retention"].create({
            "type_retention": "iva", "type": "in_invoice",
            "company_id": self.company.id, "partner_id": self.partner_pnr_75.id,
            "date": fields.Date.today(), "date_accounting": fields.Date.today(),
            "number": "SHARED-NUMBER",
        })

        self.assertEqual(islr_retention.number, iva_retention.number)
        _logger.info("========= test_same_number_different_type_retention_allowed passed =========")
