from odoo.tests import TransactionCase, tagged


@tagged("l10n_ve_accountant", "credit_limit", "-at_install", "post_install")
class TestCreditLimitScope(TransactionCase):
    """The credit limit must only gate documents that increase the receivable.

    Before this scope existed the check ran over every move type, so credit
    notes, payments and IVA/ISLR withholding vouchers were rejected for a
    customer that was already over the limit -- blocking exactly the documents
    used to bring the balance back down.
    """

    def _move(self, move_type):
        return self.env["account.move"].new({"move_type": move_type})

    def test_customer_invoice_is_checked(self):
        self.assertTrue(self._move("out_invoice")._is_subject_to_credit_limit())

    def test_customer_receipt_is_checked(self):
        self.assertTrue(self._move("out_receipt")._is_subject_to_credit_limit())

    def test_credit_note_is_not_checked(self):
        """Credit notes reduce the receivable, so they must never be blocked."""
        self.assertFalse(self._move("out_refund")._is_subject_to_credit_limit())

    def test_journal_entry_is_not_checked(self):
        """Payments, advances and withholding vouchers are posted as entries."""
        self.assertFalse(self._move("entry")._is_subject_to_credit_limit())

    def test_vendor_documents_are_not_checked(self):
        for move_type in ("in_invoice", "in_refund", "in_receipt"):
            with self.subTest(move_type=move_type):
                self.assertFalse(self._move(move_type)._is_subject_to_credit_limit())

    def test_context_key_waives_the_check(self):
        """skip_credit_limit_check lets an authorized flow post a blocked invoice."""
        move = self._move("out_invoice")
        self.assertTrue(move._is_subject_to_credit_limit())
        waived = move.with_context(skip_credit_limit_check=True)
        self.assertFalse(waived._is_subject_to_credit_limit())

    def test_context_key_is_not_set_by_default(self):
        """The waiver must be opt-in, never inherited from an ambient context."""
        self.assertFalse(self.env.context.get("skip_credit_limit_check"))
