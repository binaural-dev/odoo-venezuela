from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_stock_account.tests.common import StockAccountTestCommon


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationCreditNoteRegression(StockAccountTestCommon):
    """Ticket #13965: `l10n_ve_invoice` validates, when a credit note
    (out_refund) is posted, that it doesn't use a product absent on the
    invoice it reverses nor credit more than it. `l10n_ve_donation.
    _reverse_moves()` builds exactly that kind of credit note, but always
    with a dedicated donation product, never the product of the original
    invoice -- so it is exempted through `is_donation` (see
    `_l10n_ve_skip_refund_origin_validation()`). This is the regression
    Manuel Guerrero's review (16 ago 2026) flagged as missing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.expense_account = cls.env["account.account"].search(
            [("account_type", "=", "expense"), ("company_ids", "in", cls.company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Donation Expense Test",
            "code": "DONTEST01",
            "account_type": "expense",
        })
        cls.company.donation_account_id = cls.expense_account.id

        # An income account is required on the invoice-line's product so
        # the generated `account.move.line` has a non-null `account_id`
        # (a minimal database has no default income account to fall back
        # on via the product category).
        cls.income_account = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_ids", "in", cls.company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Donation Credit Note Test Income",
            "code": "DONCNINC01",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })

        cls.donation_product = cls.env["product.template"].create({
            "name": "Producto de Donación",
            "type": "service",
            "is_donation_product": True,
            "property_account_income_id": cls.income_account.id,
        })

        cls.regular_product = cls.env["product.product"].create({
            "name": "Producto Regular",
            "type": "service",
            "property_account_income_id": cls.income_account.id,
        })

        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["account.journal"].create({
            "name": "Donation Credit Note Test Journal",
            "type": "sale",
            "code": "DONCNJ",
            "company_id": cls.company.id,
        })

    def _create_donation_invoice(self):
        company_partner = self.company.partner_id
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "is_donation": True,
            "partner_id": company_partner.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.regular_product.id,
                    "quantity": 1,
                    "price_unit": 100.0,
                })
            ],
        })

    def _create_donation_credit_note(self, invoice, is_donation, price_unit):
        return self.env["account.move"].create({
            "move_type": "out_refund",
            "is_donation": is_donation,
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal.id,
            "reversed_entry_id": invoice.id,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.donation_product.product_variant_ids[:1].id,
                    "quantity": 1,
                    "price_unit": price_unit,
                })
            ],
        })

    def _post_donation_invoice(self, invoice):
        """Posting a donation invoice: the first `action_post()` stops at
        the `l10n_ve_accountant` alert wizard (it returns an action and
        posts nothing); the wizard calls it again with the context key."""
        result = invoice.action_post()
        self.assertIsInstance(result, dict)
        self.assertEqual(invoice.state, "draft")
        invoice.with_context(move_action_post_alert=True).action_post()

    def test_donation_reversal_creates_credit_note_with_donation_product(self):
        """Fix: the automatic reversal must succeed even though the credit
        note's product (donation product) differs from the invoice's
        product (regular product). The credit note is posted in the same
        call, with no `l10n_ve_skip_refund_origin_validation` key in the
        context: only `is_donation` keeps it exempt."""
        invoice = self._create_donation_invoice()
        self._post_donation_invoice(invoice)

        credit_note = self.env["account.move"].search([
            ("reversed_entry_id", "=", invoice.id),
            ("move_type", "=", "out_refund"),
        ], limit=1)

        self.assertTrue(credit_note, "The donation invoice was not auto-reversed into a credit note.")
        self.assertEqual(
            credit_note.invoice_line_ids.mapped("product_id"),
            self.donation_product.product_variant_ids,
        )
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(credit_note.state, "posted")

    def test_donation_credit_note_mirrors_the_invoice_amounts(self):
        """The automatic credit note must carry the amounts of the invoice:
        the same total, a tax line and a receivable line. Created with
        `skip_invoice_sync` the core generated neither the tax nor the
        payment term line and the credit note stayed at zero."""
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "is_donation": True,
            "partner_id": self.company.partner_id.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "invoice_line_ids": [
                Command.create({
                    "product_id": self.regular_product.id,
                    "quantity": 2,
                    "price_unit": 100.0,
                    "tax_ids": [Command.set(self.sale_tax.ids)],
                })
            ],
        })
        self._post_donation_invoice(invoice)
        credit_note = self.env["account.move"].search([
            ("reversed_entry_id", "=", invoice.id),
            ("move_type", "=", "out_refund"),
        ], limit=1)

        self.assertTrue(invoice.amount_total)
        self.assertEqual(credit_note.amount_untaxed, invoice.amount_untaxed)
        self.assertEqual(credit_note.amount_tax, invoice.amount_tax)
        self.assertEqual(credit_note.amount_total, invoice.amount_total)
        self.assertEqual(
            sorted(credit_note.line_ids.mapped("display_type")),
            ["payment_term", "product", "tax"],
        )
        receivable = credit_note.line_ids.filtered(lambda l: l.display_type == "payment_term")
        invoice_receivable = invoice.line_ids.filtered(lambda l: l.display_type == "payment_term")
        # `balance` is in the company currency, `amount_total` in the one of
        # the document: the receivable lines are compared with each other.
        self.assertEqual(receivable.balance, -invoice_receivable.balance)
        self.assertEqual(sum(credit_note.line_ids.mapped("balance")), 0.0)

    def test_donation_credit_note_posted_later_without_context_key(self):
        """A donation credit note left in draft (e.g. created by
        `_reverse_moves`) is posted later, in a separate call that no
        longer carries any context key. `is_donation` alone must keep it
        exempt from the origin validation, which runs at posting time."""
        invoice = self._create_donation_invoice()
        self._post_donation_invoice(invoice)
        credit_note = self.env["account.move"].search([
            ("reversed_entry_id", "=", invoice.id),
            ("move_type", "=", "out_refund"),
        ], limit=1)
        credit_note.button_draft()
        self.assertEqual(credit_note.state, "draft")

        credit_note._post(soft=False)
        self.assertEqual(credit_note.state, "posted")

    def test_reverse_moves_without_default_values(self):
        """`_reverse_moves()` builds the credit note even when the caller
        passes no `default_values_list`."""
        invoice = self._create_donation_invoice()
        self._post_donation_invoice(invoice)
        credit_note = invoice._reverse_moves()
        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertTrue(credit_note.is_donation)
        self.assertEqual(credit_note.reversed_entry_id, invoice)

    def test_reverse_moves_of_a_mixed_batch_reverses_every_invoice(self):
        """A batch with a donation invoice and a regular one: the donation
        invoice gets its donation credit note and the regular one is
        reversed by the standard flow (it used to be skipped silently)."""
        donation_invoice = self._create_donation_invoice()
        self._post_donation_invoice(donation_invoice)
        regular_invoice = self._create_donation_invoice()
        regular_invoice.is_donation = False
        regular_invoice.action_post()
        regular_invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(regular_invoice.state, "posted")

        reversed_moves = (donation_invoice | regular_invoice)._reverse_moves(
            [{"ref": "Donation reversal"}, {"ref": "Regular reversal"}]
        )

        self.assertEqual(len(reversed_moves), 2)
        donation_note = reversed_moves.filtered(lambda m: m.reversed_entry_id == donation_invoice)
        regular_note = reversed_moves.filtered(lambda m: m.reversed_entry_id == regular_invoice)
        self.assertEqual(len(donation_note), 1)
        self.assertTrue(donation_note.is_donation)
        self.assertEqual(
            donation_note.invoice_line_ids.mapped("product_id"),
            self.donation_product.product_variant_ids,
        )
        self.assertEqual(len(regular_note), 1)
        self.assertFalse(regular_note.is_donation)
        self.assertEqual(regular_note.move_type, "out_refund")
        self.assertEqual(regular_note.ref, "Regular reversal")
        self.assertEqual(
            regular_note.invoice_line_ids.mapped("product_id"), self.regular_product
        )

    def test_is_donation_exempts_credit_note_from_origin_validation(self):
        """Guard: proves *why* the `is_donation` exemption is necessary.
        The same credit note, crediting more than the origin invoice with
        a product the invoice never had, is rejected at posting time when
        it is not a donation, and accepted when it is."""
        invoice = self._create_donation_invoice()
        self._post_donation_invoice(invoice)

        regular_credit_note = self._create_donation_credit_note(
            invoice, is_donation=False, price_unit=150.0
        )
        with self.assertRaises(ValidationError):
            regular_credit_note._post(soft=False)

        donation_credit_note = self._create_donation_credit_note(
            invoice, is_donation=True, price_unit=150.0
        )
        donation_credit_note._post(soft=False)
        self.assertEqual(donation_credit_note.state, "posted")
