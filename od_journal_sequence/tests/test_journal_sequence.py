from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "od_journal_sequence")
class TestJournalSequence(TransactionCase):
    """Sequence of a journal and of its entries.

    The tests build their own journal and accounts. The accounting test base of Odoo creates a
    company, a chart and products with its own user, and the Venezuelan localization rejects them
    when it is installed: only support users create sale and purchase journals, and a product
    takes a single tax.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env["account.journal"].create({
            "name": "Sequence Journal",
            "code": "SQJ",
            "type": "general",
        })
        cls.income_account, cls.expense_account = cls.env["account.account"].create([
            {"name": "Sequence income", "code": "SQJ4001", "account_type": "income"},
            {"name": "Sequence expense", "code": "SQJ6001", "account_type": "expense"},
        ])

    def test_new_journal_gets_entry_sequence(self):
        self.assertTrue(self.journal.sequence_id)
        self.assertEqual(self.journal.sequence_id.prefix, "SQJ/%(range_year)s/")
        self.assertEqual(self.journal.sequence_id.implementation, "no_gap")

    def test_journal_cannot_lose_its_sequence(self):
        with self.assertRaises(ValidationError):
            self.journal.sequence_id = False

    def test_posted_entry_takes_the_journal_sequence(self):
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal.id,
            "date": "2026-11-09",
            "line_ids": [
                Command.create({"account_id": self.income_account.id, "debit": 100.0}),
                Command.create({"account_id": self.expense_account.id, "credit": 100.0}),
            ],
        })
        move.action_post()
        self.assertTrue(move.name.startswith(f"{self.journal.code}/2026/"), move.name)

    def test_account_manager_cannot_use_resequence_wizard(self):
        manager = self.env["res.users"].create({
            "name": "Accounting Manager",
            "login": "accounting_manager_seq",
            "group_ids": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("account.group_account_manager").id,
            ])],
            "company_ids": [Command.set(self.env.company.ids)],
            "company_id": self.env.company.id,
        })
        with self.assertRaises(AccessError):
            self.env["account.resequence.wizard"].with_user(manager).check_access("create")
