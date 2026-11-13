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

    def _receipt(self, partner=True, origin=None, product=None, quantity=2.0, is_donation=True):
        product = product or self.product_storable
        origin = origin or self.location_received
        dest = self.warehouse_donation.lot_stock_id
        return self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_receipt.id,
            "location_id": origin.id,
            "location_dest_id": dest.id,
            "partner_id": self.donor.id if partner else False,
            "is_donation": is_donation,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": quantity,
                "product_uom": product.uom_id.id,
                "location_id": origin.id,
                "location_dest_id": dest.id,
            })],
        })

    def _validate(self, picking):
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({"quantity": picking.move_ids.product_uom_qty, "picked": True})
        picking.button_validate()

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

    def test_03_without_received_donations_accounts_it_is_refused(self):
        self.company.donation_income_account_ids = False
        picking = self._receipt()
        with self.assertRaisesRegex(UserError, "no received donations accounts"):
            self._validate(picking)

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
        product = self.env["product.product"].create({"name": "Consumable", "type": "consu"})
        picking = self._receipt(origin=self.warehouse_donation.lot_stock_id, product=product)
        self._validate(picking)
        self.assertEqual(picking.state, "done")

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
        self.assertIn("Certificado de Donación", html)
        self.assertIn(self.donor.name, html)
        self.assertIn("Av. Principal 1", html)
        self.assertIn("los siguientes bienes", html)
        self.assertIn("Total at cost", html)
        self.assertIn("Valor al costo", html)
        self.assertIn(self.product_storable.name, html)
        self.assertNotIn("la suma de", html)

    def test_12_receipt_amounts_come_from_the_value_of_the_moves(self):
        picking = self._receipt(quantity=2.0)
        self._validate(picking)
        amounts = picking._get_donation_receipt_amounts()
        self.assertAlmostEqual(amounts["amount"], 2.0 * self.product_storable.standard_price)
        self.assertAlmostEqual(amounts["amount"], picking._get_donation_grand_total())

    def test_13_each_document_has_its_picking(self):
        receipt = self._receipt()
        self._validate(receipt)
        delivery = self._create_donation_picking(partner=self.partner, validate=True)
        with self.assertRaisesRegex(UserError, "Donation Certificate"):
            receipt.print_donation_receipt()
        with self.assertRaisesRegex(UserError, "not a donation receipt"):
            delivery.print_donation_certificate()
        self.assertIsInstance(delivery.print_donation_receipt(), dict)

    def test_14_the_form_offers_the_certificate_only_for_receipts(self):
        arch = self.env["stock.picking"].get_view(
            self.env.ref("stock.view_picking_form").id, "form"
        )["arch"]
        self.assertIn('name="print_donation_certificate"', arch)
        self.assertIn("picking_type_code != 'incoming'", arch)
