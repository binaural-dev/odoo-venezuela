from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged("l10n_ve_donation", "received_donation", "-at_install", "post_install")
class TestReceivedDonation(TestDonationCommon):
    """Donations RECEIVED by the company: the direction is told by the
    income accounts of the company, and the lines of their entries carry the
    donor (the lines of the donations given carry the company)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_account = cls.env["account.account"].create({
            "name": "Bank Test",
            "code": "DON100001",
            "account_type": "asset_cash",
            "company_ids": [Command.set([cls.company.id])],
        })
        cls.donor = cls.env["res.partner"].create({"name": "Donor Test", "vat": "V12345678"})

    def _entry_vals(self, account_credit=None, donor=True, is_donation=True, ref="Entry Ref"):
        partner = {"partner_id": self.donor.id} if donor else {}
        return {
            "move_type": "entry",
            "is_donation": is_donation,
            "journal_id": self.journal_general.id,
            "ref": ref,
            "line_ids": [
                Command.create({
                    "account_id": self.bank_account.id, "debit": 100, "credit": 0,
                    "name": "Bank", **partner,
                }),
                Command.create({
                    "account_id": (account_credit or self.account_income).id,
                    "debit": 0, "credit": 100, "name": "Donation income", **partner,
                }),
            ],
        }

    def test_01_without_income_accounts_no_entry_is_a_received_donation(self):
        self.assertFalse(self.company.donation_income_account_ids)
        move = self.env["account.move"].create(self._entry_vals(donor=False))
        self.assertFalse(move._is_incoming_donation())
        self.assertFalse(move.is_incoming_donation)

    def test_02_entry_with_an_income_account_is_a_received_donation(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        self.assertTrue(move._is_incoming_donation())
        self.assertTrue(move.is_incoming_donation)

    def test_03_several_income_accounts(self):
        other_income = self.env["account.account"].create({
            "name": "Income Test 2",
            "code": "DON410002",
            "account_type": "income",
            "company_ids": [Command.set([self.company.id])],
        })
        self.company.donation_income_account_ids = self.account_income | other_income
        move = self.env["account.move"].create(self._entry_vals(account_credit=other_income))
        self.assertTrue(move.is_incoming_donation)

    def test_04_it_follows_the_accounts_of_the_company(self):
        move = self.env["account.move"].create(self._entry_vals(donor=False))
        self.assertFalse(move.is_incoming_donation)
        self.company.donation_income_account_ids = self.account_income
        self.assertTrue(move.is_incoming_donation)
        self.company.donation_income_account_ids = False
        self.assertFalse(move.is_incoming_donation)

    def test_05_it_requires_the_donation_mark(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals(is_donation=False))
        self.assertFalse(move.is_incoming_donation)
        move.is_donation = True
        self.assertTrue(move.is_incoming_donation)

    def test_06_a_donation_invoice_is_not_a_received_donation(self):
        """The donation invoice (given) uses the income account through the
        donation product: it is not a received donation."""
        self.company.donation_income_account_ids = self.account_income
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.product_donation.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account_income.id,
            })],
        })
        self.assertFalse(invoice.is_incoming_donation)

    def test_07_settings_expose_the_income_accounts(self):
        self.company.donation_income_account_ids = self.account_income
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.donation_income_account_ids, self.account_income)

    def test_08_the_lines_of_a_received_donation_carry_the_donor(self):
        """The constraint of the donations given (lines with the company)
        does not apply to a received donation."""
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        self.assertEqual(move.line_ids.partner_id, self.donor)
        move.line_ids[0].partner_id = self.partner
        self.assertEqual(move.line_ids[0].partner_id, self.partner)

    def test_09_the_lines_of_a_received_donation_are_not_filled_with_the_company(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals(donor=False))
        self.assertFalse(move.line_ids.partner_id)
        move.line_ids.partner_id = False
        move.is_donation = True
        self.assertFalse(move.line_ids.partner_id)

    def test_10_the_donations_given_keep_the_company_on_their_lines(self):
        """The same lines on a donation that is not received: the donor in
        a line is rejected and the empty ones are filled with the company."""
        with self.assertRaises(ValidationError):
            self.env["account.move"].create(self._entry_vals())
        move = self.env["account.move"].create(self._entry_vals(donor=False))
        self.assertEqual(move.line_ids.partner_id, self.company.partner_id)
