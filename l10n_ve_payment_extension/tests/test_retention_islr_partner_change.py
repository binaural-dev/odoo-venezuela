import logging

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)

ISLR_FORM_VIEW = "l10n_ve_payment_extension.view_retention_islr_form_l10n_ve_payment_extension"


@tagged("post_install", "-at_install", "retention_islr_partner_change")
class TestRetentionIslrPartnerChange(RetentionTestCommon):
    """Regression tests for helpdesk #15341: an ISLR retention allowed
    confirming with lines from invoices of a different partner than the
    one selected on the retention.

    Before the fix, `onchange_partner_id` only reloaded/cleared lines for
    `type_retention == "iva"`, so switching the partner on a draft ISLR
    retention left stale lines pointing to the previous partner's invoices
    (UI path). There was also no server-side guard stopping a retention
    from being saved/confirmed with mismatched lines regardless of how
    they got there (hard guard, any entry point).
    """

    def test_islr_lines_cleared_when_partner_changes(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        self._prepare_invoice_for_retention(inv)
        inv.action_post()

        other_partner = self.env["res.partner"].create({
            "name": "Otro Proveedor ISLR Test",
            "vat": "J000111333",
        })

        with Form(
            self.env["account.retention"].with_context(
                default_type="in_invoice", default_type_retention="islr",
            ),
            view=ISLR_FORM_VIEW,
        ) as retention_form:
            retention_form.partner_id = self.partner_pnr_75
            with retention_form.retention_line_ids.new() as line:
                line.move_id = inv

        retention = retention_form.save()
        self.assertTrue(retention.retention_line_ids)

        with Form(retention, view=ISLR_FORM_VIEW) as retention_form_edit:
            retention_form_edit.partner_id = other_partner

        retention = retention_form_edit.save()
        self.assertFalse(retention.retention_line_ids)
        _logger.info("========= test_islr_lines_cleared_when_partner_changes passed =========")

    def test_mismatched_partner_lines_blocked_on_save(self):
        inv = self._create_invoice_islr(
            500, self.partner_pnr_75, "in_invoice", self.purchase_journal,
        )
        self._prepare_invoice_for_retention(inv)
        inv.action_post()

        other_partner = self.env["res.partner"].create({
            "name": "Otro Proveedor ISLR Test 2",
            "vat": "J000111444",
        })

        with self.assertRaises(ValidationError):
            self.env["account.retention"].create({
                "type_retention": "islr", "type": "in_invoice",
                "company_id": self.company.id, "partner_id": other_partner.id,
                "date": fields.Date.today(), "date_accounting": fields.Date.today(),
                "retention_line_ids": [Command.create({
                    "move_id": inv.id, "payment_concept_id": self.concept_one.id,
                    "invoice_type": "in_invoice", "name": "Test",
                    "invoice_amount": 500.0, "invoice_total": 500.0,
                    "retention_amount": 15.0,
                })],
            })
        _logger.info("========= test_mismatched_partner_lines_blocked_on_save passed =========")
