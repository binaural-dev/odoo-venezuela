from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
from unittest.mock import patch


@tagged("post_install", "-at_install", "account_move")
class AccountMoveTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Configure the pos config
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "Test POS Config",
                "company_id": cls.company.id,
            }
        )

        # Create a POS session
        cls.pos_session = cls.env["pos.session"].create(
            {
                "config_id": cls.pos_config.id,
                "user_id": cls.env.uid,
            }
        )

        # Set up an account and a journal to create an account.move
        cls.account = cls.env["account.account"].create(
            {
                "name": "Test Account",
                "code": "TEST999",
                "account_type": "asset_current",
            }
        )
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal",
                "code": "TESTJ",
                "type": "general",
                "company_id": cls.company.id,
            }
        )

        # Create a journal entry
        cls.move = cls.env["account.move"].create(
            {
                "journal_id": cls.journal.id,
                "state": "draft",
                "line_ids": [
                    (0, 0, {"account_id": cls.account.id, "name": "line 1", "debit": 100}),
                    (0, 0, {"account_id": cls.account.id, "name": "line 2", "credit": 100}),
                ],
            }
        )
        cls.move.action_post()

        # Another move to simulate unrelated moves
        cls.unrelated_move = cls.env["account.move"].create(
            {
                "journal_id": cls.journal.id,
                "state": "draft",
                "line_ids": [
                    (0, 0, {"account_id": cls.account.id, "name": "line 1", "debit": 50}),
                    (0, 0, {"account_id": cls.account.id, "name": "line 2", "credit": 50}),
                ],
            }
        )
        cls.unrelated_move.action_post()

    def test_01_button_draft_with_open_session_and_restriction(self):
        """Test that a UserError is raised when trying to draft a move linked to an open session and restriction is on"""
        self.company.pos_move_to_draft = False
        self.pos_session.state = "opened"

        PosSessionClass = type(self.env["pos.session"])
        with patch.object(PosSessionClass, "_get_related_account_moves", return_value=self.move):
            with self.assertRaisesRegex(
                UserError,
                "You cannot modify a journal entry linked to a POS session that is still opened",
            ):
                self.move.button_draft()

    def test_02_button_draft_with_open_session_and_no_restriction(self):
        """Test that the move can be drafted if restriction is off, even with open session"""
        self.company.pos_move_to_draft = True
        self.pos_session.state = "opened"

        PosSessionClass = type(self.env["pos.session"])
        with patch.object(PosSessionClass, "_get_related_account_moves", return_value=self.move):
            self.move.button_draft()
            self.assertEqual(self.move.state, "draft")

    def test_03_button_draft_with_closed_session(self):
        """Test that the move can be drafted if the session is closed"""
        self.company.pos_move_to_draft = False
        self.pos_session.state = "closed"

        # When session is closed, the query `[("state", "=", "opened")]` returns nothing.
        # Thus the loop in button_draft is skipped. We don't even need to mock but we can.
        PosSessionClass = type(self.env["pos.session"])
        with patch.object(PosSessionClass, "_get_related_account_moves", return_value=self.move):
            self.move.button_draft()
            self.assertEqual(self.move.state, "draft")

    def test_04_button_draft_unrelated_move(self):
        """Test that an unrelated move can be drafted"""
        self.company.pos_move_to_draft = False
        self.pos_session.state = "opened"

        # Mock returns self.move, so unrelated_move is not in the related moves list
        PosSessionClass = type(self.env["pos.session"])
        with patch.object(PosSessionClass, "_get_related_account_moves", return_value=self.move):
            self.unrelated_move.button_draft()
            self.assertEqual(self.unrelated_move.state, "draft")
