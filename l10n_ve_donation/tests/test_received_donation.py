from datetime import datetime
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools.misc import format_date

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
        cls.donor = cls.env["res.partner"].create({"name": "Donor Test", "vat": "12345678"})

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
        does not apply to a received donation, also when a line is updated
        as the web client does."""
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        self.assertEqual(move.line_ids.partner_id, self.donor)
        line = move.line_ids[0]
        move.write({"line_ids": [Command.update(line.id, {"partner_id": self.partner.id})]})
        self.assertEqual(line.partner_id, self.partner)
        # Control: the same update on a donation given is rejected.
        given = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=self.account_expense)
        )
        with self.assertRaises(ValidationError):
            given.write({"line_ids": [Command.update(given.line_ids[0].id, {"partner_id": self.partner.id})]})

    def test_09_the_lines_of_a_received_donation_are_not_filled_with_the_company(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals(donor=False, is_donation=False))
        self.assertFalse(move.line_ids.partner_id)
        move.is_donation = True
        self.assertTrue(move.is_incoming_donation)
        self.assertFalse(move.line_ids.partner_id)
        # Control: marking a donation given fills the company.
        given = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=self.account_expense, is_donation=False)
        )
        given.is_donation = True
        self.assertEqual(given.line_ids.partner_id, self.company.partner_id)

    def test_10_the_donations_given_keep_the_company_on_their_lines(self):
        """The same lines on a donation that is not received: the donor in
        a line is rejected and the empty ones are filled with the company."""
        with self.assertRaises(ValidationError):
            self.env["account.move"].create(self._entry_vals())
        move = self.env["account.move"].create(self._entry_vals(donor=False))
        self.assertEqual(move.line_ids.partner_id, self.company.partner_id)

    # ── posting ──

    def _post(self, move):
        move.with_context(move_action_post_alert=True).action_post()

    def test_11_posting_requires_the_donor_in_every_line(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals(donor=False))
        with self.assertRaisesRegex(UserError, "donor as contact"):
            self._post(move)
        self.assertEqual(move.state, "draft")
        self.assertFalse(move.line_ids.partner_id)

    def test_12_posting_rejects_the_company_as_the_donor(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        move.line_ids[0].partner_id = self.company.partner_id
        with self.assertRaisesRegex(UserError, "donor as contact"):
            self._post(move)

    def test_13_posting_requires_the_same_donor_in_every_line(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        move.line_ids[0].partner_id = self.partner
        with self.assertRaisesRegex(UserError, "same donor"):
            self._post(move)

    def test_14_a_received_donation_is_posted_keeping_the_donor(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        self._post(move)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.line_ids.partner_id, self.donor)

    def test_15_a_received_donation_is_posted_in_a_hashed_journal(self):
        """Nothing is written to the lines when it is posted."""
        self.company.donation_income_account_ids = self.account_income
        journal = self.env["account.journal"].create({
            "name": "Hashed Received Journal",
            "code": "HRJ",
            "type": "general",
            "company_id": self.company.id,
            "restrict_mode_hash_table": True,
        })
        vals = self._entry_vals()
        vals["journal_id"] = journal.id
        move = self.env["account.move"].create(vals)
        self._post(move)
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.line_ids.partner_id, self.donor)

    def test_16_a_donation_given_is_not_checked_for_the_donor(self):
        move = self.env["account.move"].create(self._entry_vals(donor=False, account_credit=self.account_expense))
        self._post(move)
        self.assertEqual(move.state, "posted")

    def test_17_the_donor_check_runs_when_posting_without_action_post(self):
        """The check is in `_post`: it also covers the posting that does not
        go through `action_post` (the automatic posting of the drafts)."""
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals(donor=False))
        with self.assertRaisesRegex(UserError, "donor as contact"):
            move._post(soft=False)
        self.assertEqual(move.state, "draft")
        move.line_ids.partner_id = self.donor
        move._post(soft=False)
        self.assertEqual(move.state, "posted")

    def test_17b_the_extension_point_is_called_when_posting(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        with patch.object(
            type(move), "_check_incoming_donation_before_post", autospec=True
        ) as check:
            self._post(move)
        check.assert_called_once()

    # ── donor and certificate ──

    def test_18_counterparty_is_the_header_or_the_donor_of_the_lines(self):
        """The header wins, as in 17; without it (or with the company) the
        donor of the lines."""
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        self.assertEqual(move._get_donation_counterparty(), self.donor)
        move.partner_id = self.partner
        self.assertEqual(move._get_donation_counterparty(), self.partner)
        move.partner_id = self.company.partner_id
        self.assertEqual(move._get_donation_counterparty(), self.donor)

    def test_19_certificate_of_a_received_donation(self):
        self.company.donation_income_account_ids = self.account_income
        self.donor.write({"street": "Av. Principal 1", "phone": "0414-1234567"})
        move = self.env["account.move"].create(self._entry_vals(ref="Aporte para el comedor"))
        self._post(move)
        report = self.env.ref("l10n_ve_donation.action_donation_certificate_account_move")
        html, _ = report._render_qweb_html(report.report_name, move.ids)
        html = html.decode()
        self.assertIn("Donation Certificate", html)
        self.assertIn(self.donor.name, html)
        self.assertIn("V-12345678", html)
        self.assertIn("Av. Principal 1", html)
        self.assertIn("the sum of", html)
        self.assertIn("I receive as a DONATION", html)
        self.assertNotIn("goods", html)
        # The legal data of the company and the extra data are extension points.
        self.assertIn('id="donation_certificate_legal"', html)
        self.assertIn('id="donation_certificate_extra"', html)

    def test_20_each_document_has_its_entry(self):
        """The certificate is the document of a donation received and the
        receipt the one of a donation given."""
        self.company.donation_income_account_ids = self.account_income
        received = self.env["account.move"].create(self._entry_vals())
        self._post(received)
        given = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=self.account_expense)
        )
        self._post(given)

        self.assertIsInstance(received.print_donation_certificate(), dict)
        with self.assertRaisesRegex(UserError, "Donation Certificate"):
            received.print_donation_receipt()
        self.assertIsInstance(given.print_donation_receipt(), dict)
        with self.assertRaisesRegex(UserError, "not a donation received"):
            given.print_donation_certificate()

    def test_21_the_form_offers_the_certificate_only_for_received_donations(self):
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        self.assertIn('name="print_donation_certificate"', arch)
        self.assertIn("is_stock_valuation_entry or not is_incoming_donation", arch)
        self.assertIn("is_stock_valuation_entry or is_incoming_donation", arch)



    # ── direction changes, guards and beneficiary ──

    def test_22_a_donation_given_that_becomes_received_needs_the_donor_to_post(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=self.account_expense)
        )
        self.assertEqual(move.line_ids.partner_id, self.company.partner_id)
        credit_line = move.line_ids.filtered("credit")
        move.write({"line_ids": [Command.update(credit_line.id, {"account_id": self.account_income.id})]})
        self.assertTrue(move.is_incoming_donation)
        with self.assertRaisesRegex(UserError, "donor as contact"):
            self._post(move)

    def test_23_a_donation_received_that_becomes_given_rejects_the_donor_in_the_lines(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        credit_line = move.line_ids.filtered("credit")
        with self.assertRaises(ValidationError):
            move.write({"line_ids": [Command.update(credit_line.id, {"account_id": self.account_expense.id})]})

    def test_24_the_accounts_of_the_company_of_the_entry_decide(self):
        """An account shared by two companies that is a received donations
        account only of company A does not make an entry of company B a
        donation received."""
        company_b = self.env["res.company"].create({"name": "Company B"})
        Account = self.env["account.account"]

        def shared_account(name, code, account_type):
            account = Account.create({
                "name": name, "code": code, "account_type": account_type,
                "company_ids": [Command.set([self.company.id])],
            })
            account.with_company(company_b).code = code
            account.company_ids = [Command.link(company_b.id)]
            return account

        income = shared_account("Shared Income", "DON410099", "income")
        bank = shared_account("Shared Asset", "DON100099", "asset_current")
        journal_b = self.env["account.journal"].create({
            "name": "General B", "type": "general", "code": "GENB", "company_id": company_b.id,
        })
        self.company.donation_income_account_ids = income
        vals = self._entry_vals(account_credit=income)
        vals["line_ids"][0][2]["account_id"] = bank.id
        entry_a = self.env["account.move"].create(vals)
        # In company B the same account does not identify a donation received:
        # its lines carry the company (a donation given), not the donor.
        vals_b = self._entry_vals(donor=False, account_credit=income)
        vals_b["line_ids"][0][2]["account_id"] = bank.id
        entry_b = self.env["account.move"].with_company(company_b).create(
            {**vals_b, "journal_id": journal_b.id, "company_id": company_b.id}
        )
        self.assertEqual(entry_b.company_id, company_b)
        self.assertEqual(entry_b.line_ids.partner_id, company_b.partner_id)
        self.assertTrue(entry_a._is_incoming_donation())
        self.assertFalse(entry_b._is_incoming_donation())

    def test_25_the_print_methods_check_the_entry(self):
        self.company.donation_income_account_ids = self.account_income
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal_sale.id,
            "is_donation": True,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "product_id": self.product_donation.id, "quantity": 1, "price_unit": 100,
            })],
        })
        with self.assertRaisesRegex(UserError, "not a donation"):
            invoice.print_donation_receipt()
        regular = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=self.account_expense, is_donation=False)
        )
        self._post(regular)
        with self.assertRaisesRegex(UserError, "not a donation"):
            regular.print_donation_receipt()
        with self.assertRaisesRegex(UserError, "not a donation received"):
            regular.print_donation_certificate()
        given = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=self.account_expense)
        )
        with self.assertRaisesRegex(UserError, "once the entry is posted"):
            given.print_donation_receipt()
        received = self.env["account.move"].create(self._entry_vals())
        with self.assertRaisesRegex(UserError, "once the entry is posted"):
            received.print_donation_certificate()

    def test_25b_a_reversal_has_no_donation_document(self):
        """The reversal of a donation copies the mark and the accounts of the
        entry it cancels, so it must not offer (or print) a Donation
        Certificate or Receipt of its own."""
        self.company.donation_income_account_ids = self.account_income
        received = self.env["account.move"].create(self._entry_vals())
        self._post(received)
        given = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=self.account_expense)
        )
        self._post(given)
        today = fields.Date.today()
        received_reversal = received._reverse_moves([{"date": today}])
        given_reversal = given._reverse_moves([{"date": today}])
        self._post(received_reversal)
        self._post(given_reversal)
        # The reversal looks like a donation of its own...
        self.assertTrue(received_reversal.is_incoming_donation)
        # ...but the originals keep their documents and the reversals have none.
        self.assertIsInstance(received.print_donation_certificate(), dict)
        self.assertIsInstance(given.print_donation_receipt(), dict)
        with self.assertRaisesRegex(UserError, "reversal of"):
            received_reversal.print_donation_certificate()
        with self.assertRaisesRegex(UserError, "reversal of"):
            given_reversal.print_donation_receipt()
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        self.assertEqual(arch.count("or reversed_entry_id\""), 2)

    def test_26_the_beneficiary_of_a_donation_given_is_the_contact_of_the_header(self):
        """The lines keep the company; the beneficiary stays in the header,
        also when the entry is created with it and the lines copy it."""
        vals = self._entry_vals(donor=False, account_credit=self.account_expense)
        vals["partner_id"] = self.partner.id
        move = self.env["account.move"].create(vals)
        self.assertEqual(move.partner_id, self.partner)
        self.assertEqual(move.line_ids.partner_id, self.company.partner_id)
        self._post(move)
        self.assertEqual(move._get_donation_beneficiary(), self.partner)
        report = self.env.ref("l10n_ve_donation.action_donation_receipt_account_move")
        html, _ = report._render_qweb_html(report.report_name, move.ids)
        self.assertIn(self.partner.name, html.decode())
        # A beneficiary that is a child contact: the lines copy its commercial
        # partner (the parent), which is not the company either.
        parent = self.env["res.partner"].create({"name": "Hospital X", "is_company": True})
        child = self.env["res.partner"].create({"name": "Dr. Perez", "parent_id": parent.id, "type": "contact"})
        self.assertEqual(child.commercial_partner_id, parent)
        vals_child = self._entry_vals(donor=False, account_credit=self.account_expense)
        vals_child["partner_id"] = child.id
        move_child = self.env["account.move"].create(vals_child)
        self.assertEqual(move_child.partner_id, child)
        self.assertEqual(move_child.line_ids.partner_id, self.company.partner_id)
        self._post(move_child)
        self.assertEqual(move_child._get_donation_beneficiary(), child)
        # The RIF of a child contact is the one of its commercial partner, with
        # the prefix of that partner (the child only copies the number).
        parent.write({"prefix_vat": "J", "vat": "987654321"})
        child.invalidate_recordset()
        report = self.env.ref("l10n_ve_donation.action_donation_receipt_account_move")
        html, _ = report._render_qweb_html(report.report_name, move_child.ids)
        self.assertIn("J-987654321", html.decode())
        self.assertNotIn("V-987654321", html.decode())
        # A different contact in a line is still rejected.
        with self.assertRaises(ValidationError):
            move2 = self.env["account.move"].create(vals)
            move2.write({"line_ids": [Command.update(move2.line_ids[0].id, {"partner_id": self.donor.id})]})

    def test_26c_marking_the_entry_as_donation_replaces_the_lines_that_copied_the_header(self):
        """An entry created without the mark and with a contact in the header
        has its lines on the commercial partner of that contact: marking it as
        a donation gives them the company, as when it is created marked."""
        parent = self.env["res.partner"].create({"name": "Marked Hospital", "is_company": True})
        child = self.env["res.partner"].create({"name": "Marked Doctor", "parent_id": parent.id, "type": "contact"})
        for beneficiary in (parent, child):
            with self.subTest(beneficiary=beneficiary.name):
                vals = self._entry_vals(donor=False, account_credit=self.account_expense, is_donation=False)
                vals["partner_id"] = beneficiary.id
                move = self.env["account.move"].create(vals)
                self.assertEqual(move.line_ids.partner_id, parent)
                move.write({"is_donation": True})
                self.assertEqual(move.partner_id, beneficiary)
                self.assertEqual(move.line_ids.partner_id, self.company.partner_id)
        # A contact that is not the one of the header is still rejected.
        vals = self._entry_vals(donor=False, account_credit=self.account_expense, is_donation=False)
        vals["line_ids"][0][2]["partner_id"] = self.donor.id
        move = self.env["account.move"].create(vals)
        with self.assertRaises(ValidationError):
            move.write({"is_donation": True})
        # A received donation (the donor in the lines) is not replaced.
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals(is_donation=False))
        move.write({"is_donation": True})
        self.assertEqual(move.line_ids.partner_id, self.donor)
        self.assertTrue(move.is_incoming_donation)

    def test_26b_the_certificate_shows_the_rif_of_the_commercial_partner_of_a_child_donor(self):
        parent = self.env["res.partner"].create({
            "name": "Donor Company", "is_company": True, "prefix_vat": "J", "vat": "987654322",
        })
        child = self.env["res.partner"].create({"name": "Donor Contact", "parent_id": parent.id, "type": "contact"})
        self.company.donation_income_account_ids = self.account_income
        vals = self._entry_vals()
        for command in vals["line_ids"]:
            command[2]["partner_id"] = child.id
        move = self.env["account.move"].create(vals)
        self._post(move)
        report = self.env.ref("l10n_ve_donation.action_donation_certificate_account_move")
        html, _ = report._render_qweb_html(report.report_name, move.ids)
        self.assertIn("J-987654322", html.decode())
        self.assertNotIn("V-987654322", html.decode())

    def test_27_the_form_shows_the_beneficiary_only_for_donations_given(self):
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        self.assertIn('string="Beneficiary"', arch)
        self.assertIn("not is_donation or move_type != 'entry' or is_incoming_donation", arch)

    def test_28_the_settings_only_offer_the_accounts_of_the_company(self):
        arch = self.env["res.config.settings"].get_view(
            self.env.ref("l10n_ve_donation.l10n_ve_donation_inherit_l10n_ve_stock_account").id, "form"
        )["arch"]
        self.assertIn("company_ids", arch)
        field = self.env["res.config.settings"]._fields["donation_income_account_ids"]
        self.assertTrue(field.check_company)


    def _assert_accounts_change_rejected(self, accounts):
        """The write fails and, as the request would, is rolled back."""
        with self.assertRaisesRegex(ValidationError, "cannot change"):
            with self.env.cr.savepoint():
                self.company.donation_income_account_ids = accounts
        self.assertEqual(self.company.donation_income_account_ids, self.account_income)

    def test_29_the_accounts_cannot_change_while_posted_donations_use_them(self):
        """Removing an account that a posted donation received uses, or adding
        one that a posted donation given uses, would change the document of
        those entries: it is rejected. Drafts and unused accounts are free."""
        self.company.donation_income_account_ids = self.account_income
        received = self.env["account.move"].create(self._entry_vals())
        # A draft does not block the change.
        other = self.env["account.account"].create({
            "name": "Income Other", "code": "DON410002", "account_type": "income",
            "company_ids": [Command.set([self.company.id])],
        })
        self.company.donation_income_account_ids = self.account_income | other
        self.company.donation_income_account_ids = self.account_income
        self._post(received)
        self._assert_accounts_change_rejected(other)
        self._assert_accounts_change_rejected(self.env["account.account"])
        # Adding an account that a posted donation given uses is rejected too.
        given = self.env["account.move"].create(
            self._entry_vals(donor=False, account_credit=other)
        )
        self._post(given)
        self._assert_accounts_change_rejected(self.account_income | other)
        # An account no posted donation uses can be added and removed.
        unused = self.env["account.account"].create({
            "name": "Income Unused", "code": "DON410003", "account_type": "income",
            "company_ids": [Command.set([self.company.id])],
        })
        self.company.donation_income_account_ids = self.account_income | unused
        self.company.donation_income_account_ids = self.account_income
        # Writing other fields of the company is not affected.
        self.company.write({"name": self.company.name})


@tagged("l10n_ve_donation", "received_donation", "-at_install", "post_install")
class TestReceivedDonationPicking(TestDonationCommon):
    """Receipt of goods donated to the company: the origin is an `inventory`
    location whose valuation account is a received donations account (the
    stock valuation credits it)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.donation_income_account_ids = cls.account_income
        cls.donor = cls.env["res.partner"].create({"name": "Donor Test", "vat": "V12345678"})
        cls.location_received = cls.env["stock.location"].create({
            "name": "Donations received",
            "usage": "inventory",
            "location_id": cls.warehouse_donation.view_location_id.id,
            "company_id": cls.company.id,
            "valuation_account_id": cls.account_income.id,
        })
        cls.picking_type_receipt = cls.env["stock.picking.type"].create({
            "name": "Donation Receipt",
            "code": "incoming",
            "warehouse_id": cls.warehouse_donation.id,
            "sequence_code": "DWHRCV",
            "default_location_src_id": cls.location_received.id,
            "default_location_dest_id": cls.warehouse_donation.lot_stock_id.id,
            "is_donation_picking_type": True,
        })

    def _receipt(self, partner=True, origin=None, product=None, quantity=2.0, is_donation=True, extra=()):
        product = product or self.product_storable
        origin = origin or self.location_received
        dest = self.warehouse_donation.lot_stock_id
        return self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_receipt.id,
            "location_id": origin.id,
            "location_dest_id": dest.id,
            "partner_id": self.donor.id if partner else False,
            "is_donation": is_donation,
            "move_ids": [
                Command.create({
                    "product_id": line_product.id,
                    "product_uom_qty": line_quantity,
                    "product_uom": line_product.uom_id.id,
                    "location_id": origin.id,
                    "location_dest_id": dest.id,
                })
                for line_product, line_quantity in ((product, quantity), *extra)
            ],
        })

    def _validate(self, picking):
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.write({"quantity": move.product_uom_qty, "picked": True})
        picking.button_validate()

    def _periodic_product(self, name, cost):
        category = self.env["product.category"].create({"name": "Periodic " + name, "property_valuation": "periodic"})
        return self.env["product.product"].create({
            "name": name, "type": "consu", "is_storable": True,
            "standard_price": cost, "categ_id": category.id,
        })

    def test_01_a_donation_receipt_requires_the_donor(self):
        picking = self._receipt(partner=False)
        with self.assertRaisesRegex(UserError, "donor"):
            self._validate(picking)
        self.assertNotEqual(picking.state, "done")

    def test_02_a_correct_receipt_credits_the_received_donations_account(self):
        picking = self._receipt()
        self._validate(picking)
        self.assertEqual(picking.state, "done")
        entry = picking.move_ids.account_move_id
        self.assertEqual(len(entry), 1)
        credit = entry.line_ids.filtered("credit")
        debit = entry.line_ids.filtered("debit")
        self.assertEqual(credit.account_id, self.account_income)
        self.assertEqual(debit.account_id, self.account_stock)

    def test_03_without_received_donations_accounts_the_receipt_is_a_regular_one(self):
        """The company does not receive donations: the receipt is checked as
        any other receipt (no donor, any origin)."""
        self.company.donation_income_account_ids = False
        picking = self._receipt(partner=False, origin=self.env.ref("stock.stock_location_suppliers"))
        self.assertEqual(picking._get_donation_receipt_config_errors(), [])
        self._validate(picking)
        self.assertEqual(picking.state, "done")

    def test_04_the_origin_must_be_an_inventory_location(self):
        picking = self._receipt(origin=self.warehouse_donation.lot_stock_id)
        with self.assertRaisesRegex(UserError, "must be an Inventory Loss location"):
            self._validate(picking)

    def test_05_the_origin_needs_a_valuation_account(self):
        location = self.location_received.copy({"name": "Without account", "valuation_account_id": False})
        picking = self._receipt(origin=location)
        with self.assertRaisesRegex(UserError, "has no Stock Valuation Account"):
            self._validate(picking)

    def test_06_the_account_of_the_origin_must_be_a_received_donations_one(self):
        location = self.location_received.copy({
            "name": "Wrong account", "valuation_account_id": self.account_expense.id,
        })
        picking = self._receipt(origin=location)
        with self.assertRaisesRegex(UserError, "is not a received donations account"):
            self._validate(picking)

    def test_07_products_without_automated_valuation_are_not_checked(self):
        consumable = self.env["product.product"].create({"name": "Consumable", "type": "consu"})
        picking = self._receipt(origin=self.env.ref("stock.stock_location_suppliers"), product=consumable)
        self._validate(picking)
        self.assertEqual(picking.state, "done")
        # A storable product with periodic valuation generates no entry either.
        periodic = self._periodic_product("Periodic", 5.0)
        picking = self._receipt(origin=self.env.ref("stock.stock_location_suppliers"), product=periodic)
        self._validate(picking)
        self.assertEqual(picking.state, "done")
        self.assertFalse(picking.move_ids.account_move_id)

    def test_08_a_receipt_that_is_not_a_donation_is_not_checked(self):
        picking = self._receipt(partner=False, origin=self.warehouse_donation.lot_stock_id, is_donation=False)
        self._validate(picking)
        self.assertEqual(picking.state, "done")

    def test_09_a_donation_delivery_cannot_use_a_received_donations_account(self):
        picking = self._create_donation_picking(partner=self.partner)
        self.location_donation.valuation_account_id = self.account_income
        errors = picking._get_donation_delivery_config_errors()
        self.assertTrue(any("received donations account" in error for error in errors))
        self.location_donation.valuation_account_id = self.account_expense
        self.assertFalse(picking._get_donation_delivery_config_errors())

    def test_10_card_of_a_donation_type_marks_the_new_picking(self):
        Picking = self.env["stock.picking"]
        context = {"default_picking_type_id": self.picking_type_receipt.id}
        self.assertTrue(Picking.with_context(**context).default_get(["is_donation"])["is_donation"])
        other = {"default_picking_type_id": self.warehouse_normal.in_type_id.id}
        self.assertFalse(Picking.with_context(**other).default_get(["is_donation"]).get("is_donation"))

    def test_11_certificate_of_a_donation_receipt(self):
        self.donor.write({"street": "Av. Principal 1", "phone": "0414-1234567"})
        picking = self._receipt()
        self._validate(picking)
        action = picking.print_donation_certificate()
        report = self.env.ref("l10n_ve_donation.action_donation_certificate_stock_picking")
        self.assertEqual(action, report.report_action(picking))
        html, _ = report._render_qweb_html(report.report_name, picking.ids)
        html = html.decode()
        self.assertIn("Donation Certificate", html)
        self.assertIn(self.donor.name, html)
        self.assertIn("Av. Principal 1", html)
        self.assertIn("the following goods", html)
        # The total of the shared table is shown once; the equivalent apart.
        self.assertEqual(html.count("Total at cost"), 1)
        self.assertIn("Equivalent value", html)
        self.assertIn("In the city of", html)
        self.assertIn(self.product_storable.name, html)
        self.assertNotIn("the sum of", html)

    def test_11b_the_certificate_of_goods_shows_the_value_in_the_other_currency(self):
        """The shared table shows the total in the currency of the company;
        the paragraph below shows the other one: the bolivar amount when the
        company is in USD (Higea), the equivalent in USD when it is in
        bolivars. The bolivar amount is never missing."""
        usd = self.env.ref("base.USD")
        vef = self.company.currency_id
        picking = self._receipt()
        self._validate(picking)
        goods = picking._get_donation_goods_data()
        Monetary = self.env["ir.qweb.field.monetary"]

        def render(amounts, cost_currency):
            return str(self.env["ir.qweb"]._render("l10n_ve_donation.donation_certificate_body", {
                "o": picking,
                "donor": self.donor,
                "certificate_date": fields.Date.today(),
                "amounts": amounts,
                "donation_line_data": goods["lines"],
                "donation_grand_total": goods["total"],
                "donation_cost_currency": cost_currency,
            }))

        Move = self.env["account.move"]
        company_in_usd = render(Move._compute_donation_amounts(usd, vef, 100.0, 45000.0, 1 / 450, 450.0), usd)
        self.assertIn("Equivalent value", company_in_usd)
        self.assertIn(Monetary.value_to_html(45000.0, {"display_currency": vef}), company_in_usd)
        self.assertIn("450.0000", company_in_usd)

        company_in_vef = render(Move._compute_donation_amounts(vef, usd, 38000.0, 84.44, 450.0, 1 / 450), vef)
        self.assertIn("Equivalent value", company_in_vef)
        self.assertIn(Monetary.value_to_html(84.44, {"display_currency": usd}), company_in_vef)
        self.assertNotIn(Monetary.value_to_html(38000.0, {"display_currency": vef}), company_in_vef)

    def test_12_receipt_amounts_come_from_the_value_of_the_moves(self):
        picking = self._receipt(quantity=2.0)
        self._validate(picking)
        amounts = picking._get_donation_picking_amounts()
        entry = picking.move_ids.account_move_id
        self.assertAlmostEqual(amounts["amount"], 2.0 * self.product_storable.standard_price)
        self.assertAlmostEqual(amounts["amount"], picking._get_donation_grand_total())
        # The equivalent is the total at the rate stored in the entry.
        self.assertEqual(amounts["equivalent_currency"], entry.foreign_currency_id)
        self.assertAlmostEqual(amounts["equivalent_amount"], amounts["amount"] * entry.foreign_inverse_rate)
        self.assertEqual(amounts["rate"], entry.foreign_rate)

    def test_12b_a_picking_with_goods_of_both_valuations_uses_the_total_of_all_of_them(self):
        """Only the products with automated valuation generate an entry: the
        equivalent is the total of ALL the goods at the rate of that entry,
        not the alternate amount of the entry alone."""
        periodic = self._periodic_product("Periodic mixed", 5.0)
        picking = self._receipt(quantity=1.0, extra=((periodic, 2.0),))
        self._validate(picking)
        entry = picking.move_ids.account_move_id
        self.assertEqual(len(entry), 1)
        amounts = picking._get_donation_picking_amounts()
        expected_total = self.product_storable.standard_price + 2.0 * 5.0
        self.assertAlmostEqual(amounts["amount"], expected_total)
        self.assertAlmostEqual(amounts["equivalent_amount"], expected_total * entry.foreign_inverse_rate)
        self.assertNotAlmostEqual(amounts["equivalent_amount"], entry.foreign_debit)

    def test_12c_a_picking_without_entries_takes_the_rate_of_its_date(self):
        periodic = self._periodic_product("Periodic alone", 5.0)
        picking = self._receipt(origin=self.env.ref("stock.stock_location_suppliers"), product=periodic, quantity=2.0)
        self._validate(picking)
        self.assertFalse(picking.move_ids.account_move_id)
        amounts = picking._get_donation_picking_amounts()
        rates = self.env["res.currency.rate"].compute_rate(
            self.company.foreign_currency_id.id, picking._get_donation_document_date()
        )
        self.assertEqual(amounts["equivalent_currency"], self.company.foreign_currency_id)
        self.assertEqual(amounts["rate"], rates["foreign_rate"])
        self.assertAlmostEqual(amounts["equivalent_amount"], 10.0 * rates["foreign_inverse_rate"])
        # Without a rate for the day the equivalent is omitted.
        with patch.object(type(self.env["res.currency.rate"]), "compute_rate", return_value={}):
            amounts = picking._get_donation_picking_amounts()
        self.assertFalse(amounts["equivalent_currency"])
        self.assertAlmostEqual(amounts["amount"], 10.0)

    def test_12d_the_goods_of_the_document_are_computed_once_for_the_report(self):
        picking = self._receipt()
        self._validate(picking)
        original = type(picking)._get_donation_product_lines
        with patch.object(
            type(picking), "_get_donation_product_lines", autospec=True, side_effect=original
        ) as lines:
            report = self.env.ref("l10n_ve_donation.action_donation_certificate_stock_picking")
            report._render_qweb_html(report.report_name, picking.ids)
        self.assertEqual(lines.call_count, 1)

    def test_12e_the_documents_show_the_local_date_of_the_picking(self):
        """`date_done` is stored in UTC: 02:30 UTC of the 14th is the 13th in
        Caracas (UTC-4), and both documents show the 13th."""
        self.env.user.tz = "America/Caracas"
        receipt = self._receipt()
        self._validate(receipt)
        receipt.date_done = datetime(2026, 11, 14, 2, 30)
        report = self.env.ref("l10n_ve_donation.action_donation_certificate_stock_picking")
        html, _ = report._render_qweb_html(report.report_name, receipt.ids)
        self.assertIn("13/11/2026", html.decode())
        self.assertNotIn("14/11/2026", html.decode())

        delivery = self._create_donation_picking(partner=self.partner, validate=True)
        delivery.date_done = datetime(2026, 11, 14, 2, 30)
        report = self.env.ref("l10n_ve_donation.action_donation_receipt_stock_picking")
        html, _ = report._render_qweb_html(report.report_name, delivery.ids)
        local = format_date(self.env, datetime(2026, 11, 14, 2, 30))
        self.assertEqual(local, format_date(self.env, datetime(2026, 11, 13).date()))
        self.assertIn(local, html.decode())

    def test_13_each_document_has_its_picking(self):
        receipt = self._receipt()
        self._validate(receipt)
        delivery = self._create_donation_picking(partner=self.partner, validate=True)
        with self.assertRaisesRegex(UserError, "Donation Certificate"):
            receipt.print_donation_receipt()
        with self.assertRaisesRegex(UserError, "not a donation reception"):
            delivery.print_donation_certificate()
        self.assertIsInstance(delivery.print_donation_receipt(), dict)

    def test_14_the_form_offers_the_certificate_only_for_receipts(self):
        arch = self.env["stock.picking"].get_view(
            self.env.ref("stock.view_picking_form").id, "form"
        )["arch"]
        self.assertIn('name="print_donation_certificate"', arch)
        self.assertIn("picking_type_code != 'incoming'", arch)

    def test_14b_without_received_donations_accounts_the_certificate_is_not_offered(self):
        """The company that does not receive donations is inert: its
        receptions have no certificate, neither the button nor the method."""
        picking = self._receipt()
        self._validate(picking)
        self.assertTrue(picking.has_donation_income_accounts)
        self.assertIsInstance(picking.print_donation_certificate(), dict)
        self.company.donation_income_account_ids = False
        self.assertFalse(picking.has_donation_income_accounts)
        with self.assertRaisesRegex(UserError, "no received donations accounts"):
            picking.print_donation_certificate()
        arch = self.env["stock.picking"].get_view(
            self.env.ref("stock.view_picking_form").id, "form"
        )["arch"]
        self.assertIn("not has_donation_income_accounts", arch)

    def test_15_the_print_methods_check_the_picking(self):
        draft_receipt = self._receipt()
        with self.assertRaisesRegex(UserError, "once the reception is done"):
            draft_receipt.print_donation_certificate()
        draft_delivery = self._create_donation_picking(partner=self.partner)
        with self.assertRaisesRegex(UserError, "once the delivery is done"):
            draft_delivery.print_donation_receipt()
        regular = self._receipt(partner=False, origin=self.warehouse_donation.lot_stock_id, is_donation=False)
        with self.assertRaisesRegex(UserError, "not a donation reception"):
            regular.print_donation_certificate()
        with self.assertRaisesRegex(UserError, "not a donation delivery"):
            regular.print_donation_receipt()

