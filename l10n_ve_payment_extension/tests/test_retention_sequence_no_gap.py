from odoo.tests import tagged
from odoo import _
from odoo.exceptions import UserError
from .test_withholding_common_VEF import RetentionTestCommon
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_sequence_no_gap")
class TestRetentionSequenceNoGap(RetentionTestCommon):
    """
    Regression test for TI-15000: retention control-number sequences
    (retention.iva.control.number / retention.islr.control.number /
    retention.municipal.control.number) leaving a gap in the numbering when
    the transaction that creates the `account.retention` is rolled back.

    Fixed in `l10n_ve_payment_extension/data/sequence_data.xml` by setting
    `implementation="no_gap"` on the three sequences. With the default
    ("standard") implementation, PostgreSQL's `nextval()` is NOT
    transactional: the counter keeps its increment even if the surrounding
    transaction (and therefore the retention record itself) is rolled back,
    producing a permanent gap in the legal numbering. `no_gap` instead reads
    / updates the counter with a row-level `SELECT ... FOR UPDATE`, so the
    increment participates in the transaction and is reverted together with
    everything else on rollback.

    Note: as of this writing, `l10n_ve_payment_extension` itself has no
    phone/email validation blocking retention creation/confirmation (the
    reported trigger for the original bug). That check only exists in the
    optional `l10n_ve_invoice_digital` module (`get_subject_retention()`),
    and only fires when digitizing the document with The Factory HKA, not
    on `account.retention.create()`. To keep this test self-contained
    within `l10n_ve_payment_extension` while still exercising exactly the
    mechanism the fix addresses, we use a partner without
    phone/mobile/email (as described in the reported bug) and force the
    rollback with an explicit `cr.savepoint()` around the failure, which is
    the same primitive Odoo relies on to unwind a whole request when an
    unhandled exception (e.g. a validation `UserError`) is raised.
    """

    def test_01_partner_without_contact_data(self):
        partner = self.partner_pnr_75
        self.assertFalse(partner.phone)
        self.assertFalse(partner.email)
        _logger.info("========= test_01_partner_without_contact_data passed =========")

    def test_02_sequence_number_not_consumed_on_rollback(self):
        partner = self.partner_pnr_75
        invoice = self._create_invoice_reten_iva(
            amount=200, partner=partner,
            out_invoice="in_invoice", journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()

        sequence = self.env["account.retention"].get_sequence_retention("iva")
        self.assertEqual(
            sequence.implementation, "no_gap",
            "The retention.iva.control.number sequence must use the "
            "no_gap implementation for the numbering to be transactional.",
        )
        next_before = sequence.number_next_actual

        retention_id = None
        with self.assertRaises(UserError):
            with self.env.cr.savepoint():
                retention = self._create_iva_retention(invoice)
                retention_id = retention.id
                # The number was consumed as part of create() -> _set_sequence().
                # no_gap advances the counter via a direct SQL UPDATE (not the
                # ORM), so the cached number_next_actual must be invalidated
                # to see the new value.
                self.assertTrue(retention.number)
                sequence.invalidate_recordset(["number_next_actual"])
                self.assertNotEqual(sequence.number_next_actual, next_before)

                # Simulates the validation that, per the reported bug,
                # prevented confirming the retention (e.g. missing
                # phone/email) and made the whole request/transaction roll
                # back after the number had already been consumed.
                raise UserError(
                    _(
                        "The partner '%s' has no phone/email configured; "
                        "the retention cannot be confirmed."
                    )
                    % partner.name
                )

        # The savepoint rollback must have discarded the retention record...
        self.assertTrue(retention_id)
        self.assertFalse(
            self.env["account.retention"].browse(retention_id).exists()
        )

        # ...and, thanks to no_gap, the sequence counter as well.
        sequence.invalidate_recordset(["number_next_actual"])
        next_after = sequence.number_next_actual
        self.assertEqual(
            next_after, next_before,
            "The IVA retention sequence must not advance when the "
            "transaction that consumed it is rolled back (no_gap "
            "implementation).",
        )

        _logger.info(
            "========= test_02_sequence_number_not_consumed_on_rollback passed ========="
        )
