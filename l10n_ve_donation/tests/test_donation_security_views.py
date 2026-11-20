import importlib.util
from pathlib import Path

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from odoo.addons.l10n_ve_donation import _post_init_hook
from odoo.addons.l10n_ve_donation.tests.common import TestDonationCommon


def _load_migration(name):
    path = Path(__file__).parents[1] / "migrations" / "19.0.3.0.1" / "post-migration.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationSecurityAndViews(TestDonationCommon):
    """Group of the Donation Manager, the buttons of the entry form and who
    can reverse or reset to draft a donation entry.

    Covers: REQ-DON-030, REQ-DON-032, REQ-DON-034.
    """

    def test_manager_group_has_a_privilege_of_its_own(self):
        # REQ-DON-034
        """Inside the Accounting privilege the group was one more option of the
        same selector of the user form (saving the user with another level
        removed it); without privilege it is only drawn in developer mode. It
        has a privilege of its own: a selector independent of Accounting, in
        the permissions tab."""
        group = self.env.ref("l10n_ve_donation.group_donation_manager")
        accounting = self.env.ref("account.res_groups_privilege_accounting")
        self.assertTrue(group.privilege_id)
        self.assertNotEqual(group.privilege_id, accounting)
        self.assertEqual(group.privilege_id.group_ids, group)
        self.assertEqual(group.privilege_id.category_id, accounting.category_id)
        self.assertIn(self.env.ref("base.user_admin"), group.user_ids)

    def test_post_init_hook_adds_the_administrator_to_the_group(self):
        # REQ-DON-034
        group = self.env.ref("l10n_ve_donation.group_donation_manager")
        group.user_ids = [Command.clear()]
        _post_init_hook(self.env)
        users = group.with_context(active_test=False).user_ids
        self.assertIn(self.env.ref("base.user_admin"), users)
        self.assertIn(self.env.ref("base.user_root"), users)

    def test_migration_moves_the_manager_group_to_its_privilege(self):
        # REQ-DON-034
        """The databases that already have the module keep the old privilege
        (the record was `noupdate`): the migration moves the group and
        releases the record."""
        group = self.env.ref("l10n_ve_donation.group_donation_manager")
        group.privilege_id = self.env.ref("account.res_groups_privilege_accounting")
        _load_migration("donation_post_migration").migrate(self.env.cr, "19.0.3.0.0")
        group.invalidate_recordset()
        self.assertEqual(
            group.privilege_id, self.env.ref("l10n_ve_donation.res_groups_privilege_donation")
        )
        self.env.cr.execute(
            "SELECT noupdate FROM ir_model_data WHERE module = 'l10n_ve_donation' "
            "AND name = 'group_donation_manager'"
        )
        self.assertFalse(self.env.cr.fetchone()[0])

    def test_certificate_is_letter_size_and_the_receipt_half_letter(self):
        # REQ-DON-032
        """The certificate goes in letter size, as the receipt goes in half
        letter."""
        for xmlid in (
            "l10n_ve_donation.action_donation_certificate_account_move",
            "l10n_ve_donation.action_donation_certificate_stock_picking",
        ):
            self.assertEqual(self.env.ref(xmlid).paperformat_id.format, "Letter")
        for xmlid in (
            "l10n_ve_donation.action_donation_receipt_account_move",
            "l10n_ve_donation.action_donation_receipt_stock_picking",
        ):
            paperformat = self.env.ref(xmlid).paperformat_id
            self.assertEqual((paperformat.format, paperformat.page_width, paperformat.page_height),
                             ("custom", 216, 140))

    def test_migration_changes_an_a4_certificate_to_letter_only(self):
        # REQ-DON-032
        """A format that somebody chose on purpose is left alone."""
        paperformat = self.env.ref("l10n_ve_donation.paperformat_donation_certificate")
        migration = _load_migration("donation_post_migration_paper")
        paperformat.format = "A4"
        migration.migrate(self.env.cr, "19.0.3.0.0")
        paperformat.invalidate_recordset()
        self.assertEqual(paperformat.format, "Letter")
        paperformat.format = "A5"
        migration.migrate(self.env.cr, "19.0.3.0.0")
        paperformat.invalidate_recordset()
        self.assertEqual(paperformat.format, "A5")

    def _get_button_condition(self, string):
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        buttons = etree.fromstring(arch).xpath(f"//button[@string='{string}']")
        self.assertEqual(len(buttons), 1)
        return buttons[0].get("invisible")

    def _is_hidden(self, condition, **values):
        values.setdefault("payment_state", "not_paid")
        return bool(safe_eval(condition, values))

    def test_reverse_button_keeps_the_standard_condition(self):
        # REQ-DON-034
        """The button is only for the posted entries that are not reversed:
        the condition of the donations replaced the standard one and the
        button showed in any draft entry (and failed when it was pressed)."""
        condition = self._get_button_condition("Reverse Entry")
        entry = {"move_type": "entry", "state": "posted", "is_donation": False,
                 "can_reverse_donation_move": False}
        self.assertFalse(self._is_hidden(condition, **entry))
        self.assertTrue(self._is_hidden(condition, **{**entry, "state": "draft"}))
        self.assertTrue(self._is_hidden(condition, **{**entry, "payment_state": "reversed"}))
        self.assertTrue(self._is_hidden(condition, **{**entry, "move_type": "out_invoice"}))

    def test_reverse_button_of_a_donation_is_for_the_manager(self):
        # REQ-DON-034
        condition = self._get_button_condition("Reverse Entry")
        donation = {"move_type": "entry", "state": "posted", "is_donation": True}
        self.assertTrue(self._is_hidden(condition, **donation, can_reverse_donation_move=False))
        self.assertFalse(self._is_hidden(condition, **donation, can_reverse_donation_move=True))
        draft = {**donation, "state": "draft"}
        self.assertTrue(self._is_hidden(condition, **draft, can_reverse_donation_move=True))

    def test_reset_to_draft_button_keeps_the_standard_condition(self):
        # REQ-DON-034
        """The standard condition (hash, lock dates...) is kept and the
        donations and the sales invoices are hidden on top of it."""
        condition = self._get_button_condition("Reset to Draft")
        entry = {"move_type": "entry", "state": "posted", "is_donation": False,
                 "show_reset_to_draft_button": True}
        self.assertFalse(self._is_hidden(condition, **entry))
        self.assertTrue(self._is_hidden(condition, **{**entry, "show_reset_to_draft_button": False}))
        self.assertTrue(self._is_hidden(condition, **{**entry, "is_donation": True}))
        self.assertTrue(self._is_hidden(condition, **{**entry, "move_type": "out_invoice"}))

    # ── the reversal and the reset to draft are checked in the server too ──

    def _user(self, login, manager=False):
        groups = (
            self.env.ref("base.group_user")
            | self.env.ref("account.group_account_invoice")
            | self.env.ref("stock.group_stock_user")
        )
        if manager:
            # The localization also asks an accountant to change a validated entry.
            groups |= (
                self.env.ref("l10n_ve_donation.group_donation_manager")
                | self.env.ref("account.group_account_manager")
            )
        return self.env["res.users"].create({
            "name": login, "login": login, "company_id": self.company.id,
            "company_ids": [Command.set(self.company.ids)],
            "group_ids": [Command.set(groups.ids)],
        })

    def _entry(self, is_donation=True):
        move = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": is_donation,
            "journal_id": self.journal_general.id,
            "ref": "Gift",
            "line_ids": [
                Command.create({"account_id": self.account_expense.id, "debit": 100, "credit": 0}),
                Command.create({"account_id": self.account_receivable.id, "debit": 0, "credit": 100}),
            ],
        })
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def test_only_the_manager_reverses_a_donation_entry(self):
        # REQ-DON-030
        """The button is hidden for the others, but the action is also in the
        list view and any call reaches the method."""
        entry = self._entry()
        other = self._user("not.manager")
        manager = self._user("manager", manager=True)
        with self.assertRaisesRegex(UserError, "Only the Donation Manager"):
            entry.with_user(other)._reverse_moves()
        self.assertTrue(entry.with_user(manager)._reverse_moves())
        # What runs as superuser is not restricted.
        self.assertTrue(self._entry()._reverse_moves())

    def test_a_regular_entry_is_reversed_by_anybody(self):
        # REQ-DON-030
        entry = self._entry(is_donation=False)
        self.assertTrue(entry.with_user(self._user("not.manager"))._reverse_moves())

    def test_only_the_manager_resets_a_donation_entry_to_draft(self):
        # REQ-DON-030
        entry = self._entry()
        with self.assertRaisesRegex(UserError, "Only the Donation Manager"):
            entry.with_user(self._user("not.manager")).button_draft()
        self.assertEqual(entry.state, "posted")
        entry.with_user(self._user("manager", manager=True)).button_draft()
        self.assertEqual(entry.state, "draft")
