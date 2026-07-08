from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountMoveExtended(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company.currency_id = self.currency_vef
        self.company.foreign_currency_id = self.currency_usd

        self.account_receivable = self.env["account.account"].create(
            {
                "name": "Receivable Test",
                "code": "990001",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_revenue = self.env["account.account"].create(
            {
                "name": "Revenue Test",
                "code": "990002",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_expense = self.env["account.account"].create(
            {
                "name": "Expense Test",
                "code": "990003",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_payable = self.env["account.account"].create(
            {
                "name": "Payable Test",
                "code": "990004",
                "account_type": "liability_payable",
                "reconcile": True,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "property_account_receivable_id": self.account_receivable.id,
                "property_account_payable_id": self.account_payable.id,
            }
        )

        self.tax_sale = self.env["account.tax"].create(
            {
                "name": "IVA 16% Sale",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
            }
        )
        self.tax_purchase = self.env["account.tax"].create(
            {
                "name": "IVA 16% Purchase",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "service",
                "list_price": 100,
                "taxes_id": [(6, 0, [self.tax_sale.id])],
                "property_account_income_id": self.account_revenue.id,
                "property_account_expense_id": self.account_expense.id,
                "supplier_taxes_id": [(6, 0, [self.tax_purchase.id])],
            }
        )

        self.journal_sale = self.env["account.journal"].create(
            {
                "name": "Sale Journal Extended",
                "type": "sale",
                "code": "XSLJ",
                "company_id": self.company.id,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.journal_purchase = self.env["account.journal"].create(
            {
                "name": "Purchase Journal Extended",
                "type": "purchase",
                "code": "XPRJ",
                "company_id": self.company.id,
                "default_account_id": self.account_expense.id,
            }
        )
        self.journal_contingency = self.env["account.journal"].create(
            {
                "name": "Contingency Journal",
                "type": "sale",
                "code": "XCNJ",
                "company_id": self.company.id,
                "is_contingency": True,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.journal_debit = self.env["account.journal"].create(
            {
                "name": "Debit Journal",
                "type": "sale",
                "code": "XDBJ",
                "company_id": self.company.id,
                "is_debit": True,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.journal_purchase_intl = self.env["account.journal"].create(
            {
                "name": "International Purchase Journal",
                "type": "purchase",
                "code": "XITJ",
                "company_id": self.company.id,
                "is_purchase_international": True,
                "default_account_id": self.account_expense.id,
            }
        )

    # --- _check_price_in_zero ---

    def test_price_in_zero(self):
        self.company.max_product_invoice = 10
        with self.assertRaises(ValidationError):
            self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "journal_id": self.journal_sale.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_date_display": fields.Date.today(),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "quantity": 1,
                                "price_unit": 0,
                                "tax_ids": [(6, 0, [self.tax_sale.id])],
                            },
                        )
                    ],
                }
            )

    def test_price_in_zero_ignores_section_and_note(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "Section",
                            "price_unit": 0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "display_type": "line_note",
                            "name": "Note",
                            "price_unit": 0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_sale.id])],
                        },
                    ),
                ],
            }
        )
        self.assertTrue(invoice, "Invoice with section and note should be created")

    # --- _compute_is_debit_journal ---

    def test_is_debit_journal_false(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        self.assertFalse(invoice.is_debit_journal)

    def test_is_debit_journal_true(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_debit.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        self.assertTrue(invoice.is_debit_journal)

    # --- _compute_display_date_warning ---

    def test_display_date_warning_past_date_draft(self):
        past_date = fields.Date.today() - timedelta(days=5)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": past_date,
                "invoice_date_display": past_date,
            }
        )
        self.assertEqual(invoice.state, "draft")
        self.assertTrue(invoice.display_date_warning)

    def test_display_date_warning_today_no_warning(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        self.assertFalse(invoice.display_date_warning)

    # --- _compute_next_installment_date ---

    def test_next_installment_date_defaults_to_due_date(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        self.assertEqual(invoice.next_installment_date, invoice.invoice_date_due)

    # --- _onchange_invoice_line_ids ---

    def test_onchange_max_products(self):
        self.company.max_product_invoice = 3
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        invoice.invoice_line_ids = [
            (
                0,
                0,
                {
                    "product_id": self.product.id,
                    "quantity": i + 1,
                    "price_unit": 100,
                    "tax_ids": [(6, 0, [self.tax_sale.id])],
                },
            )
            for i in range(4)
        ]
        with self.assertRaises(ValidationError):
            invoice._onchange_invoice_line_ids()

    def test_onchange_max_products_within_limit(self):
        self.company.max_product_invoice = 10
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": i + 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_sale.id])],
                        },
                    )
                    for i in range(3)
                ],
            }
        )
        self.assertEqual(len(invoice.invoice_line_ids), 3)

    def test_onchange_max_products_only_sales(self):
        self.company.max_product_invoice = 1
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_purchase.id])],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 2,
                            "price_unit": 200,
                            "tax_ids": [(6, 0, [self.tax_purchase.id])],
                        },
                    ),
                ],
            }
        )
        self.assertEqual(
            len(invoice.invoice_line_ids), 2, "Purchase invoices should not be limited"
        )

    # --- _check_correlative ---

    def test_contingency_requires_correlative(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_contingency.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )

        with self.assertRaises(ValidationError):
            invoice._check_correlative()

    def test_contingency_allows_correlative(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_contingency.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "correlative": "00001",
            }
        )
        try:
            invoice._check_correlative()
        except (ValidationError, UserError):
            self.fail("_check_correlative() raised unexpectedly")

    def test_contingency_duplicate_correlative_same_journal(self):
        self.company.group_sales_invoicing_series = False
        self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_contingency.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "correlative": "00055",
            }
        )

        with self.assertRaises(UserError):
            self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "journal_id": self.journal_contingency.id,
                    "invoice_date": fields.Date.today(),
                    "invoice_date_display": fields.Date.today(),
                    "correlative": "00055",
                }
            )

    # --- is_valid_to_sequence ---

    def test_is_valid_to_sequence_sale_no_correlative(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        self.assertTrue(invoice.is_valid_to_sequence())

    def test_is_valid_to_sequence_already_has_correlative(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "correlative": "00099",
            }
        )
        self.assertFalse(invoice.is_valid_to_sequence())

    def test_is_valid_to_sequence_contingency_no_series(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_contingency.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        self.assertFalse(invoice.is_valid_to_sequence())

    def test_is_valid_to_sequence_purchase_journal(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        self.assertFalse(invoice.is_valid_to_sequence())

    # --- get_sequence ---

    def test_get_sequence_returns_number(self):
        self.company.group_sales_invoicing_series = False
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        seq = invoice.get_sequence()
        self.assertIsNotNone(seq)

    def test_get_sequence_with_series_enabled(self):
        self.company.group_sales_invoicing_series = True
        series_seq = self.env["ir.sequence"].create(
            {
                "name": "Series Sequence Test",
                "code": "test.series.seq",
                "padding": 5,
            }
        )
        self.journal_sale.series_correlative_sequence_id = series_seq.id
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        seq = invoice.get_sequence()
        self.assertIsNotNone(seq)

    def test_get_sequence_series_missing_raises(self):
        self.company.group_sales_invoicing_series = True
        self.journal_sale.series_correlative_sequence_id = False
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        with self.assertRaises(UserError):
            invoice.get_sequence()

    # --- create with international purchase ---

    def test_create_international_sets_correlative(self):
        decl = "C-12345-ABCDE"
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_purchase_intl.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "declaration_unique_of_customs": decl,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_purchase.id])],
                        },
                    )
                ],
            }
        )
        self.assertEqual(invoice.correlative, decl)

    # --- write sync correlative with international ---

    def test_write_syncs_correlative_on_declaration_change(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_purchase_intl.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "declaration_unique_of_customs": "D-ORIG",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_purchase.id])],
                        },
                    )
                ],
            }
        )
        self.assertEqual(invoice.correlative, "D-ORIG")
        invoice.write({"declaration_unique_of_customs": "D-NEW"})
        self.assertEqual(invoice.correlative, "D-NEW")

    # --- _check_invoice_date_display_purchases ---

    def test_purchase_display_date_exceeds_accounting_date(self):
        self.company.block_invoice_display_date_upper_than_date = True
        with self.assertRaises(ValidationError):
            self.env["account.move"].create(
                {
                    "move_type": "in_invoice",
                    "partner_id": self.partner.id,
                    "journal_id": self.journal_purchase.id,
                    "invoice_date_display": fields.Date.today(),
                    "date": fields.Date.today() + timedelta(days=-2),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "quantity": 1,
                                "price_unit": 100,
                                "tax_ids": [(6, 0, [self.tax_purchase.id])],
                            },
                        )
                    ],
                }
            )

    def test_purchase_display_date_within_limit(self):
        self.company.block_invoice_display_date_upper_than_date = True
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date_display": fields.Date.today(),
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [self.tax_purchase.id])],
                        },
                    )
                ],
            }
        )
        try:
            invoice._check_invoice_date_display_purchases()
        except ValidationError:
            self.fail("_check_invoice_date_display_purchases() raised unexpectedly")

    # --- action_debit_note_button ---

    def test_action_debit_note_button(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
            }
        )
        action = invoice.action_debit_note_button()
        self.assertIsNotNone(action)
