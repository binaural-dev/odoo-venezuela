from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationCreditNoteRegression(TransactionCase):
    """Ticket #13965: `l10n_ve_invoice` added a constrains that blocks a
    credit note (out_refund) from using a product absent on the invoice it
    reverses. `l10n_ve_donation._reverse_moves()` builds exactly that kind
    of credit note, but always with a dedicated donation product, never the
    product of the original invoice -- so without the
    `l10n_ve_skip_refund_origin_validation` bypass this reversal would
    always raise a ValidationError. This is the regression Manuel Guerrero's
    review (16 ago 2026) flagged as missing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")

        cls.expense_account = cls.env["account.account"].search(
            [("account_type", "=", "expense"), ("company_ids", "in", cls.company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Donation Expense Test",
            "code": "DONTEST01",
            "account_type": "expense",
        })
        cls.company.donation_account_id = cls.expense_account.id

        # `l10n_ve_accountant` requires every product to resolve exactly one
        # sale/purchase tax, either explicitly or via the company's default
        # fiscal configuration -- set the latter so the products below
        # (created without taxes_id/supplier_taxes_id) don't raise a
        # fiscal-inconsistency UserError. `tax_group_id` has no usable
        # default in a minimal database (no fiscal localization data
        # loaded), so pass one explicitly too.
        if not cls.company.account_sale_tax_id or not cls.company.account_purchase_tax_id:
            country_ve = cls.env.ref("base.ve")
            tax_group = cls.env["account.tax.group"].create({
                "name": "Donation Credit Note Test Tax Group",
                "country_id": country_ve.id,
            })
        if not cls.company.account_sale_tax_id:
            cls.company.account_sale_tax_id = cls.env["account.tax"].create({
                "name": "Donation Credit Note Test Sale Tax",
                "amount": 16,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
                "country_id": country_ve.id,
            })
        if not cls.company.account_purchase_tax_id:
            cls.company.account_purchase_tax_id = cls.env["account.tax"].create({
                "name": "Donation Credit Note Test Purchase Tax",
                "amount": 16,
                "type_tax_use": "purchase",
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
                "country_id": country_ve.id,
            })

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
        # Whether the move reaches "posted" depends on unrelated accounting
        # setup (chart of accounts, sequences), not on this fix -- what
        # matters here is that creating it didn't raise ValidationError.
        self.assertEqual(
            credit_note.invoice_line_ids.mapped("product_id"),
            self.donation_product.product_variant_ids,
        )

    def test_regression_without_bypass_would_block_the_reversal(self):
        """Guard: proves *why* the bypass in `_reverse_moves()` is
        necessary. Reproducing the exact same credit note but WITHOUT the
        `l10n_ve_skip_refund_origin_validation` context key must be
        rejected by `l10n_ve_invoice`'s validation, because the donation
        product is never part of the original invoice."""
        invoice = self._create_donation_invoice()
        invoice.action_post()

        with self.assertRaises(ValidationError):
            self.env["account.move"].create({
                "move_type": "out_refund",
                "is_donation": True,
                "partner_id": self.company.partner_id.id,
                "journal_id": self.journal.id,
                "reversed_entry_id": invoice.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create({
                        "product_id": self.donation_product.product_variant_ids[:1].id,
                        "quantity": 1,
                        "price_unit": 100.0,
                    })
                ],
            })
