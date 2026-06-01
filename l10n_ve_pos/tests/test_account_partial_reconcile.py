from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from unittest.mock import patch


@tagged("post_install", "-at_install", "account_partial_reconcile")
class AccountPartialReconcileTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Test POS Config",
            "company_id": cls.company.id,
        })
        cls.pos_session = cls.env["pos.session"].create({
            "config_id": cls.pos_config.id,
            "user_id": cls.env.uid,
        })

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
        })

        cls.account_receivable = cls.env["account.account"].create({
            "name": "Test Receivable",
            "code": "RECV001",
            "account_type": "asset_receivable",
        })

        cls.journal = cls.env["account.journal"].create({
            "name": "Test Journal",
            "code": "TJRN",
            "type": "general",
            "company_id": cls.company.id,
        })

        cls.move_1 = cls.env["account.move"].create({
            "journal_id": cls.journal.id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": cls.account_receivable.id, "name": "l1", "debit": 100}),
                (0, 0, {"account_id": cls.account_receivable.id, "name": "l2", "credit": 100}),
            ],
        })
        cls.move_1.action_post()

        cls.move_2 = cls.env["account.move"].create({
            "journal_id": cls.journal.id,
            "state": "draft",
            "line_ids": [
                (0, 0, {"account_id": cls.account_receivable.id, "name": "l1", "debit": 100}),
                (0, 0, {"account_id": cls.account_receivable.id, "name": "l2", "credit": 100}),
            ],
        })
        cls.move_2.action_post()

        cls.pos_order = cls.env["pos.order"].create({
            "session_id": cls.pos_session.id,
            "partner_id": cls.partner.id,
            "amount_total": 100.0,
            "amount_paid": 100.0,
            "last_order_preparation_change": False,
        })

    def _create_reconcile(self, debit_move_line, credit_move_line):
        return self.env["account.partial.reconcile"].create({
            "debit_move_id": debit_move_line.id,
            "credit_move_id": credit_move_line.id,
            "amount": 100,
            "debit_amount_currency": 100,
            "credit_amount_currency": 100,
        })

    def test_01_unlink_reconcile_allowed_when_unreconcile_flag_is_true(self):
        self.company.pos_unreconcile_moves = True
        debit_line = self.move_1.line_ids.filtered(lambda l: l.debit > 0)[0]
        credit_line = self.move_1.line_ids.filtered(lambda l: l.credit > 0)[0]
        reconcile = self._create_reconcile(debit_line, credit_line)
        reconcile.unlink()
        self.assertFalse(reconcile.exists())

    def test_02_unlink_reconcile_blocked_with_open_session(self):
        self.company.pos_unreconcile_moves = False
        self.pos_session.state = "opened"
        debit_line = self.move_1.line_ids.filtered(lambda l: l.debit > 0)[0]
        credit_line = self.move_1.line_ids.filtered(lambda l: l.credit > 0)[0]
        reconcile = self._create_reconcile(debit_line, credit_line)
        PosSessionClass = type(self.env["pos.session"])
        with patch.object(PosSessionClass, "order_ids", new=self.pos_order):
            with patch.object(type(self.pos_order), "account_move", new=self.move_1):
                with self.assertRaises(ValidationError):
                    reconcile.unlink()

    def test_03_unlink_reconcile_allowed_with_closed_session(self):
        self.company.pos_unreconcile_moves = False
        self.pos_session.state = "closed"
        debit_line = self.move_1.line_ids.filtered(lambda l: l.debit > 0)[0]
        credit_line = self.move_1.line_ids.filtered(lambda l: l.credit > 0)[0]
        reconcile = self._create_reconcile(debit_line, credit_line)
        reconcile.unlink()
        self.assertFalse(reconcile.exists())
