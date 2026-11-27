from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged("l10n_ve_donation", "expense_accounts", "-at_install", "post_install")
class TestDonationExpenseAccounts(TestDonationCommon):
    """Donation expense accounts of the company: the donations given in money
    and in kind have to use one of them (when the company lists any), and the
    default one of the donations in kind has to be one of them.

    Covers: REQ-DON-029.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_other_expense = cls.env["account.account"].create({
            "name": "Other Expense Test",
            "code": "DON610002",
            "account_type": "expense",
            "company_ids": [Command.set([cls.company.id])],
        })

    def _money_entry(self, account):
        return self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "ref": "Gift",
            "line_ids": [
                Command.create({"account_id": account.id, "debit": 100, "credit": 0, "name": "Gift"}),
                Command.create({"account_id": self.account_receivable.id, "debit": 0, "credit": 100}),
            ],
        })

    def _post(self, move):
        move.with_context(move_action_post_alert=True).action_post()

    def test_01_the_default_account_must_be_one_of_the_list(self):
        self.company.donation_expense_account_ids = self.account_expense | self.account_other_expense
        self.assertEqual(self.company.donation_account_id, self.account_expense)
        with self.assertRaisesRegex(ValidationError, "must be one of"):
            self.company.donation_account_id = self.account_stock.copy({
                "code": "DON610003", "account_type": "expense",
            })
        # Without a list there is nothing to compare with.
        self.company.donation_expense_account_ids = False
        self.company.donation_account_id = self.account_other_expense
        self.assertEqual(self.company.donation_account_id, self.account_other_expense)

    def test_02_removing_the_default_from_the_list_is_rejected(self):
        self.company.donation_expense_account_ids = self.account_expense | self.account_other_expense
        with self.assertRaisesRegex(ValidationError, "must be one of"):
            self.company.donation_expense_account_ids = self.account_other_expense

    def test_03_a_money_donation_must_use_an_account_of_the_list(self):
        self.company.donation_expense_account_ids = self.account_expense
        move = self._money_entry(self.account_other_expense)
        with self.assertRaisesRegex(UserError, "donation expense accounts"):
            self._post(move)
        self.assertEqual(move.state, "draft")
        move = self._money_entry(self.account_expense)
        self._post(move)
        self.assertEqual(move.state, "posted")

    def test_04_without_a_list_a_money_donation_has_no_restriction(self):
        self.assertFalse(self.company.donation_expense_account_ids)
        move = self._money_entry(self.account_other_expense)
        self._post(move)
        self.assertEqual(move.state, "posted")

    def test_05_the_entries_that_are_not_a_money_donation_given_are_not_checked(self):
        """A regular entry, a donation received and the reversal of a donation
        are not asked to have an expense line of the list."""
        self.company.donation_expense_account_ids = self.account_expense
        regular = self._money_entry(self.account_other_expense)
        regular.is_donation = False
        self._post(regular)
        self.assertEqual(regular.state, "posted")

        self.company.donation_income_account_ids = self.account_income
        donor = self.env["res.partner"].create({"name": "Donor Expense Test"})
        received = self.env["account.move"].create({
            "move_type": "entry",
            "is_donation": True,
            "journal_id": self.journal_general.id,
            "line_ids": [
                Command.create({"account_id": self.account_receivable.id, "debit": 100, "credit": 0,
                                "partner_id": donor.id}),
                Command.create({"account_id": self.account_income.id, "debit": 0, "credit": 100,
                                "partner_id": donor.id}),
            ],
        })
        self.assertTrue(received.is_incoming_donation)
        self._post(received)
        self.assertEqual(received.state, "posted")

        # The reversal copies the lines (the account that is not in the list
        # any more): it is posted without being asked for the list.
        given = self._money_entry(self.account_expense)
        self._post(given)
        self.company.donation_account_id = False
        self.company.donation_expense_account_ids = self.account_other_expense
        reversal = given._reverse_moves([{"ref": "Reversal"}])
        self.assertEqual(reversal.reversed_entry_id, given)
        self.assertFalse(reversal.line_ids.account_id & self.company.donation_expense_account_ids)
        reversal._post(soft=False)
        self.assertEqual(reversal.state, "posted")

    def test_06_the_destination_of_a_delivery_must_use_an_account_of_the_list(self):
        picking = self._create_donation_picking(partner=self.partner)
        self.assertFalse(picking._get_donation_delivery_config_errors())
        self.company.donation_expense_account_ids = self.account_expense
        self.assertFalse(picking._get_donation_delivery_config_errors())
        self.location_donation.valuation_account_id = self.account_other_expense
        errors = picking._get_donation_delivery_config_errors()
        self.assertTrue(any("is not a donation expense account" in error for error in errors))
        self.company.donation_expense_account_ids = False
        self.assertFalse(picking._get_donation_delivery_config_errors())

    def test_07_the_settings_check_the_default_once_all_the_fields_are_written(self):
        """The fields of the company are written one by one, in no fixed order:
        a new default account and the list that includes it can be saved
        together; a default that is not in the list is rejected."""
        new_account = self.env["account.account"].create({
            "name": "New Expense Test", "code": "DON610004", "account_type": "expense",
            "company_ids": [Command.set([self.company.id])],
        })
        self.company.donation_expense_account_ids = self.account_expense
        Settings = self.env["res.config.settings"]
        settings = Settings.create({
            "donation_account_id": new_account.id,
            "donation_expense_account_ids": [Command.set([self.account_expense.id, new_account.id])],
        })
        self.assertEqual(settings.donation_account_id, new_account)
        self.assertEqual(
            self.company.donation_expense_account_ids, self.account_expense | new_account
        )
        with self.assertRaisesRegex(ValidationError, "must be one of"):
            Settings.create({
                "donation_account_id": self.account_other_expense.id,
                "donation_expense_account_ids": [Command.set([self.account_expense.id])],
            })
