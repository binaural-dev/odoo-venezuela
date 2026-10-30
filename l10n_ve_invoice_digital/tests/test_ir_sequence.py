from odoo.tests import Form, TransactionCase, tagged
from odoo.exceptions import UserError


@tagged("post_install", "-at_install", "l10n_ve_invoice_digital", "ir_sequence")
class TestIrSequencePrefixLock(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.sequence = self.env["ir.sequence"].create(
            {"name": "Secuencia Test", "code": "test.tfhka.sequence", "prefix": "INV/"}
        )
        self.refund_sequence = self.env["ir.sequence"].create(
            {"name": "Secuencia NC Test", "code": "test.tfhka.refund.sequence", "prefix": "NC/"}
        )
        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario Test Digital",
                "code": "DTST",
                "type": "sale",
                "company_id": self.company.id,
                "digital_invoice": True,
                "sequence_id": self.sequence.id,
                "refund_sequence_id": self.refund_sequence.id,
            }
        )
        self.partner = self.env["res.partner"].create({"name": "Test Partner"})

    def test_change_prefix_without_invoices_is_allowed(self):
        self.sequence.write({"prefix": "FA-A-"})
        self.assertEqual(self.sequence.prefix, "FA-A-")

    def test_change_prefix_with_invoice_on_digital_journal_is_blocked(self):
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        with self.assertRaises(UserError):
            self.sequence.write({"prefix": "FA-A-"})
        self.assertEqual(self.sequence.prefix, "INV/")

    def test_change_refund_sequence_prefix_with_invoice_is_blocked(self):
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        with self.assertRaises(UserError):
            self.refund_sequence.write({"prefix": "NC-A-"})

    def test_change_prefix_on_non_digital_journal_is_allowed(self):
        self.journal.digital_invoice = False
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        self.sequence.write({"prefix": "FA-A-"})
        self.assertEqual(self.sequence.prefix, "FA-A-")

    def test_rewrite_same_prefix_is_allowed(self):
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        self.sequence.write({"prefix": "INV/"})
        self.assertEqual(self.sequence.prefix, "INV/")

    def test_change_other_field_with_invoice_is_allowed(self):
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        self.sequence.write({"padding": 10})
        self.assertEqual(self.sequence.padding, 10)

    # ------------------------------------------------------------------
    # prefix_locked (drives the readonly attr in the ir.sequence form)
    # ------------------------------------------------------------------

    def test_prefix_locked_false_without_invoices(self):
        self.assertFalse(self.sequence.prefix_locked)

    def test_prefix_locked_true_with_invoice_on_digital_journal(self):
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        self.assertTrue(self.sequence.prefix_locked)
        self.assertTrue(self.refund_sequence.prefix_locked)

    def test_prefix_locked_false_on_non_digital_journal(self):
        self.journal.digital_invoice = False
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        self.assertFalse(self.sequence.prefix_locked)

    def test_prefix_field_is_editable_in_form_when_not_locked(self):
        with Form(self.sequence) as sequence_form:
            sequence_form.prefix = "FA-A-"
        self.assertEqual(self.sequence.prefix, "FA-A-")

    def test_prefix_field_is_readonly_in_form_when_locked(self):
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )
        with Form(self.sequence) as sequence_form:
            with self.assertRaises(AssertionError):
                sequence_form.prefix = "FA-A-"
