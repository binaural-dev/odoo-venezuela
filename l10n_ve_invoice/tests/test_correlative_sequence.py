from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestCorrelativeSequence(TransactionCase):
    """A company can have only one active ``invoice.correlative`` sequence.

    In v17 ``check_sequence_exists`` blocked a second one; in v19 it was lost
    and ``get_sequence`` failed with "Expected singleton", so the company could
    not post invoices."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.group_sales_invoicing_series = False
        cls.env["ir.sequence"].search(
            [("code", "=", "invoice.correlative"), ("company_id", "=", cls.company.id)]
        ).unlink()
        cls.other_company = cls.env["res.company"].create({"name": "Correlative Other Co"})
        cls.partner = cls.env["res.partner"].create({"name": "Correlative Customer"})
        cls.journal = cls.env["account.journal"].create(
            {"name": "Correlative Sales", "code": "CORS", "type": "sale"}
        )

    def _create_sequence_form(self, company=None, name="Control number", active=True):
        with Form(self.env["ir.sequence"]) as form:
            form.name = name
            form.code = "invoice.correlative"
            form.padding = 5
            form.company_id = company or self.company
            form.active = active
        return form.save()

    def _invoice(self):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal.id,
            }
        )

    def test_second_active_sequence_same_company_is_rejected(self):
        self._create_sequence_form()
        with self.assertRaises(ValidationError), mute_logger("odoo.sql_db"):
            self._create_sequence_form(name="Second")

    def test_second_sequence_through_form_edit_is_rejected(self):
        self._create_sequence_form()
        inactive = self._create_sequence_form(name="Inactive", active=False)
        with self.assertRaises(ValidationError):
            with Form(inactive) as form:
                form.active = True

    def test_inactive_or_other_company_sequences_are_allowed(self):
        first = self._create_sequence_form()
        self._create_sequence_form(name="Inactive", active=False)
        other = self._create_sequence_form(company=self.other_company, name="Other co")
        self.assertTrue(first.active)
        self.assertTrue(other.active)

    def test_parent_company_and_branch_each_keep_their_own_sequence(self):
        """Native Odoo branches are child companies: the control number is
        numbered per company, so a branch has its own sequence next to its
        parent's, and still only one per branch."""
        branch = self.env["res.company"].create(
            {"name": "Correlative Branch", "parent_id": self.company.id}
        )
        parent_seq = self._create_sequence_form()
        branch_seq = self._create_sequence_form(company=branch, name="Branch")
        self.assertTrue(parent_seq.active and branch_seq.active)
        with self.assertRaises(ValidationError):
            self._create_sequence_form(company=branch, name="Branch 2")

    def test_other_codes_are_not_restricted(self):
        for index in range(2):
            self.env["ir.sequence"].create(
                {"name": f"Other {index}", "code": "zz.other.code", "company_id": self.company.id}
            )

    def test_get_sequence_returns_consecutive_numbers(self):
        sequence = self._create_sequence_form()
        invoice = self._invoice()
        first = invoice.get_sequence()
        second = invoice.get_sequence()
        self.assertEqual(first, "00001")
        self.assertEqual(second, "00002")
        self.assertEqual(sequence.number_next_actual, 3)

    def test_get_sequence_creates_the_sequence_when_missing(self):
        invoice = self._invoice()
        self.assertEqual(invoice.get_sequence(), "00001")
        self.assertEqual(
            self.env["ir.sequence"].search_count(
                [("code", "=", "invoice.correlative"), ("company_id", "=", self.company.id)]
            ),
            1,
        )

    def test_get_sequence_survives_preexisting_duplicates(self):
        """Databases migrated with two sequences (Higea company 2) must still
        post: get_sequence takes the oldest one instead of failing."""
        first = self._create_sequence_form()
        second = self.env["ir.sequence"].create(
            {"name": "Legacy", "code": "invoice.correlative", "padding": 5,
             "company_id": self.company.id, "active": False}
        )
        # Simulate the legacy state bypassing the constraint.
        self.env.cr.execute("UPDATE ir_sequence SET active = TRUE WHERE id = %s", (second.id,))
        second.invalidate_recordset()
        invoice = self._invoice()
        self.assertEqual(invoice.get_sequence(), "00001")
        first.invalidate_recordset()
        self.assertEqual(first.number_next_actual, 2)
