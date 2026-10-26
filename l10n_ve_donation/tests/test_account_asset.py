# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationAccountAsset(TransactionCase):
    """Coverage for `account.asset`'s `set_to_close`/`_get_disposal_moves`
    overrides, which propagate a disposal message to the `ref`/line names
    of the generated disposal moves.

    The enterprise disposal flow (depreciation, analytic distribution,
    currency conversion, ...) is heavy to set up for real, so the base
    `_get_disposal_moves` is mocked out: these tests isolate the donation
    override's own logic (context propagation, ref/name writes) instead of
    re-testing enterprise internals.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.asset_account = cls.env["account.account"].search(
            [("account_type", "=", "asset_fixed"), ("company_ids", "in", cls.company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Donation Asset Test",
            "code": "DONAST01",
            "account_type": "asset_fixed",
            "company_ids": [Command.set([cls.company.id])],
        })
        cls.expense_account = cls.env["account.account"].search(
            [("account_type", "=", "expense"), ("company_ids", "in", cls.company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Donation Expense Test",
            "code": "DONEXP01",
            "account_type": "expense",
            "company_ids": [Command.set([cls.company.id])],
        })
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].create({
            "name": "Donation Asset Test Journal",
            "type": "general",
            "code": "DONAJ",
            "company_id": cls.company.id,
        })

        cls.asset = cls.env["account.asset"].create({
            "name": "Donation Test Asset",
            "account_asset_id": cls.asset_account.id,
            "account_depreciation_id": cls.asset_account.id,
            "account_depreciation_expense_id": cls.expense_account.id,
            "journal_id": cls.journal.id,
            "original_value": 1000.0,
            "method_number": 5,
            "method_period": "12",
            "method": "linear",
        })

    def _create_move(self, ref):
        return self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.journal.id,
            "ref": ref,
            "line_ids": [
                Command.create({"account_id": self.expense_account.id, "name": ref, "debit": 100.0}),
                Command.create({"account_id": self.asset_account.id, "name": ref, "credit": 100.0}),
            ],
        })

    def test_get_disposal_moves_applies_message_when_present(self):
        move = self._create_move("Original ref")
        with patch(
            "odoo.addons.account_asset.models.account_asset.AccountAsset._get_disposal_moves",
            return_value=move.ids,
        ):
            result = self.asset.with_context(
                disposal_message="Donated to charity"
            )._get_disposal_moves(self.env["account.move.line"], fields.Date.today())

        self.assertEqual(result, move.ids)
        self.assertEqual(move.ref, "Donated to charity")
        self.assertTrue(
            all(name == "Donated to charity" for name in move.line_ids.mapped("name"))
        )

    def test_get_disposal_moves_leaves_moves_unchanged_without_message(self):
        move = self._create_move("Original ref")
        with patch(
            "odoo.addons.account_asset.models.account_asset.AccountAsset._get_disposal_moves",
            return_value=move.ids,
        ):
            result = self.asset._get_disposal_moves(
                self.env["account.move.line"], fields.Date.today()
            )

        self.assertEqual(result, move.ids)
        self.assertEqual(move.ref, "Original ref")

    def test_get_disposal_moves_no_op_when_no_moves_returned(self):
        with patch(
            "odoo.addons.account_asset.models.account_asset.AccountAsset._get_disposal_moves",
            return_value=[],
        ):
            result = self.asset.with_context(
                disposal_message="Donated to charity"
            )._get_disposal_moves(self.env["account.move.line"], fields.Date.today())

        self.assertEqual(result, [])

    def test_set_to_close_propagates_message_to_context(self):
        captured = {}

        def fake_get_disposal_moves(asset, invoice_lines_list, disposal_date):
            captured["message"] = asset.env.context.get("disposal_message")
            return []

        with patch.object(
            type(self.asset),
            "_get_disposal_moves",
            autospec=True,
            side_effect=fake_get_disposal_moves,
        ):
            self.asset.set_to_close(self.env["account.move.line"], message="Vehicle donated")

        self.assertEqual(captured.get("message"), "Vehicle donated")

    def test_set_to_close_without_message_does_not_set_context(self):
        captured = {}

        def fake_get_disposal_moves(asset, invoice_lines_list, disposal_date):
            captured["message"] = asset.env.context.get("disposal_message")
            return []

        with patch.object(
            type(self.asset),
            "_get_disposal_moves",
            autospec=True,
            side_effect=fake_get_disposal_moves,
        ):
            self.asset.set_to_close(self.env["account.move.line"])

        self.assertIsNone(captured.get("message"))
