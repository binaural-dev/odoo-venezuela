from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_sequence_branch")
class TestRetentionSequenceBranchFlow(RetentionTestCommon):
    """End to end: a retention issued from a branch (ticket scenario) takes
    its voucher number from the parent company correlative when
    `use_parent_retention_sequence` is set, and never creates a parallel
    sequence for the branch.
    """

    def setUp(self):
        super().setUp()
        self.parent = self.env["res.company"].create(
            {"name": "Matriz Flow", "vat": "J085025545"}
        )
        # The fixture company plays the role of the branch. Odoo forbids
        # changing the hierarchy of an existing company through the ORM, so
        # the parent link is set directly in the database (test only).
        self.company.write({"vat": "J085025545"})
        self.env.cr.execute(
            "UPDATE res_company SET parent_id = %s, parent_path = %s WHERE id = %s",
            (self.parent.id, f"{self.parent.id}/{self.company.id}/", self.company.id),
        )
        self.env.invalidate_all()
        self.assertEqual(self.company.root_id, self.parent)
        self.Retention = self.env["account.retention"]
        self.Sequence = self.env["ir.sequence"].with_context(active_test=False)

    def _count_sequences(self, company, type_retention="iva"):
        return self.Sequence.search_count(
            [
                ("code", "=", f"retention.{type_retention}.control.number"),
                ("company_id", "=", company.id),
            ]
        )

    def _issue_iva_retention(self):
        invoice = self._create_invoice_reten_iva(
            amount=200,
            partner=self.partner_pnr_75,
            out_invoice="in_invoice",
            journal=self.purchase_journal,
        )
        self._prepare_invoice_for_retention(invoice)
        invoice.action_post()
        return self._create_iva_retention(invoice)

    def test_01_branch_takes_number_from_parent_sequence(self):
        self.company.use_parent_retention_sequence = True
        branch_sequences_before = self._count_sequences(self.company)
        parent_sequence = self.Retention.with_company(
            self.parent
        ).get_sequence_retention("iva")
        parent_sequence.sudo().number_next_actual = 8786

        first = self._issue_iva_retention()
        second = self._issue_iva_retention()

        self.assertTrue(first.number.endswith("00008786"), first.number)
        self.assertTrue(second.number.endswith("00008787"), second.number)
        self.assertEqual(first.name, first.number)
        self.assertEqual(
            self._count_sequences(self.company),
            branch_sequences_before,
            "The branch must not get a parallel sequence.",
        )

    def test_02_parent_and_branch_share_consecutive_numbers(self):
        self.company.use_parent_retention_sequence = True
        parent_sequence = self.Retention.with_company(
            self.parent
        ).get_sequence_retention("iva")
        parent_sequence.sudo().number_next_actual = 100

        parent_number = parent_sequence.sudo().next_by_id()
        branch_retention = self._issue_iva_retention()
        self.assertEqual(int(parent_number), 100)
        self.assertTrue(branch_retention.number.endswith("00000101"))

    def test_03_default_keeps_independent_branch_sequence(self):
        self.assertFalse(self.company.use_parent_retention_sequence)
        parent_sequences_before = self._count_sequences(self.parent)
        retention = self._issue_iva_retention()
        self.assertEqual(self._count_sequences(self.company), 1)
        self.assertEqual(self._count_sequences(self.parent), parent_sequences_before)
        self.assertTrue(retention.number)

    def test_04_islr_and_municipal_use_parent_sequence(self):
        self.company.use_parent_retention_sequence = True
        retention = self._issue_iva_retention()
        before = {
            t: self._count_sequences(self.company, t) for t in ("islr", "municipal")
        }
        for type_retention in ("islr", "municipal"):
            retention.number = False
            retention.type_retention = type_retention
            retention._set_sequence()
            self.assertTrue(retention.number)
            self.assertEqual(
                self._count_sequences(self.company, type_retention),
                before[type_retention],
            )
            self.assertEqual(self._count_sequences(self.parent, type_retention), 1)
