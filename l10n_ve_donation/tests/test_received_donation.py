from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
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

    def test_17_the_extension_point_of_the_checks_is_a_method(self):
        self.company.donation_income_account_ids = self.account_income
        move = self.env["account.move"].create(self._entry_vals())
        move._check_incoming_donation_before_post()

    # ── donor and certificate ──

    def test_18_counterparty_is_the_header_or_the_donor_of_the_lines(self):
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
        self.assertIn("Certificado de Donación", html)
        self.assertIn(self.donor.name, html)
        self.assertIn("V12345678", html)
        self.assertIn("Av. Principal 1", html)
        self.assertIn("la suma de", html)
        self.assertIn("recibo en calidad de DONACIÓN", html)
        self.assertNotIn("bienes", html)
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

