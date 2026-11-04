from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "retention_sequence_branch")
class TestRetentionSequenceBranch(TransactionCase):
    """A native Odoo branch shares the parent company retention correlative
    only when `use_parent_retention_sequence` is set and the tax ID matches.
    Default behavior (flag off) keeps one independent sequence per company.
    """

    def setUp(self):
        super().setUp()
        self.parent = self.env["res.company"].create(
            {"name": "Matriz Test", "vat": "J085025545"}
        )
        self.branch = self.env["res.company"].create(
            {
                "name": "Sucursal Test",
                "vat": "J085025545",
                "parent_id": self.parent.id,
            }
        )
        self.Retention = self.env["account.retention"]

    def _sequence_for(self, company, type_retention="iva"):
        return self.Retention.with_company(company).get_sequence_retention(
            type_retention
        )

    def test_01_default_keeps_own_sequence(self):
        self.assertFalse(self.branch.use_parent_retention_sequence)
        sequence = self._sequence_for(self.branch)
        self.assertEqual(sequence.company_id, self.branch)

    def test_02_flag_uses_parent_sequence(self):
        self.branch.use_parent_retention_sequence = True
        for type_retention in ("iva", "islr", "municipal"):
            sequence = self._sequence_for(self.branch, type_retention)
            self.assertEqual(sequence.company_id, self.parent)
            self.assertEqual(
                sequence, self._sequence_for(self.parent, type_retention)
            )

    def test_03_shared_counter_is_consecutive(self):
        self.branch.use_parent_retention_sequence = True
        first = self._sequence_for(self.parent).next_by_id()
        second = self._sequence_for(self.branch).next_by_id()
        third = self._sequence_for(self.parent).next_by_id()
        self.assertEqual(
            [int(first) + 1, int(second) + 1], [int(second), int(third)]
        )

    def test_04_different_vat_keeps_own_sequence(self):
        self.branch.write(
            {"use_parent_retention_sequence": True, "vat": "J999999990"}
        )
        sequence = self._sequence_for(self.branch)
        self.assertEqual(sequence.company_id, self.branch)

    def test_05_company_without_parent_ignores_flag(self):
        self.parent.use_parent_retention_sequence = True
        sequence = self._sequence_for(self.parent)
        self.assertEqual(sequence.company_id, self.parent)
