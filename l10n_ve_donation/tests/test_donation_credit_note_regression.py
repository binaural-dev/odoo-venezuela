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

    def test_donation_reversal_creates_credit_note_with_donation_product(self):
        """Fix: the automatic reversal must succeed even though the credit
        note's product (donation product) differs from the invoice's
        product (regular product)."""
        invoice = self._create_donation_invoice()
        invoice.action_post()

        credit_note = self.env["account.move"].search([
            ("reversed_entry_id", "=", invoice.id),
            ("move_type", "=", "out_refund"),
        ], limit=1)

        self.assertTrue(credit_note, "The donation invoice was not auto-reversed into a credit note.")
        self.assertEqual(
            credit_note.invoice_line_ids.mapped("product_id"),
            self.donation_product.product_variant_ids,
        )

    def test_donation_credit_note_posted_later_without_context_key(self):
        """The automatic donation credit note stays in draft (its
        `action_post()` stops at the l10n_ve_accountant confirmation
        wizard), so it is posted later, in a separate call that no longer
        carries `l10n_ve_skip_refund_origin_validation`. `is_donation`
        alone must keep it exempt from the origin validation, which runs
        at posting time."""
        invoice = self._create_donation_invoice()
        invoice.action_post()
        credit_note = self.env["account.move"].search([
            ("reversed_entry_id", "=", invoice.id),
            ("move_type", "=", "out_refund"),
        ], limit=1)
        self.assertEqual(credit_note.state, "draft")

        credit_note._post(soft=False)
        self.assertEqual(credit_note.state, "posted")

    def test_is_donation_exempts_credit_note_from_origin_validation(self):
        """Guard: proves *why* the `is_donation` exemption is necessary.
        The same credit note, crediting more than the origin invoice with
        a product the invoice never had, is rejected at posting time when
        it is not a donation, and accepted when it is."""
        invoice = self._create_donation_invoice()
        invoice.action_post()

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
