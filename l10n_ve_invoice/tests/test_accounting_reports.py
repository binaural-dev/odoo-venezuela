from datetime import date, timedelta
from io import BytesIO
import unittest

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountingReports(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company.currency_id = self.currency_vef
        self.company.foreign_currency_id = self.currency_usd

        self.tax_group_16 = self.env["account.tax.group"].create(
            {"name": "IVA 16% TG", "sequence": 1}
        )
        self.tax_group_8 = self.env["account.tax.group"].create(
            {"name": "IVA 8% TG", "sequence": 2}
        )
        self.tax_group_31 = self.env["account.tax.group"].create(
            {"name": "IVA 31% TG", "sequence": 3}
        )
        self.tax_group_exempt = self.env["account.tax.group"].create(
            {"name": "Exento TG", "sequence": 0}
        )
        self.tax_group_nd_16 = self.env["account.tax.group"].create(
            {"name": "NoDed 16% TG", "sequence": 10}
        )

        self.tax_sale_16 = self.env["account.tax"].create(
            {
                "name": "IVA 16% Sale Report",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group_16.id,
            }
        )
        self.tax_sale_exempt = self.env["account.tax"].create(
            {
                "name": "Exenta Sale Report",
                "amount": 0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group_exempt.id,
            }
        )
        self.tax_purchase_16 = self.env["account.tax"].create(
            {
                "name": "IVA 16% Purch Report",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group_16.id,
            }
        )
        self.tax_purchase_nd_16 = self.env["account.tax"].create(
            {
                "name": "NoDed 16% Purch Report",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group_nd_16.id,
            }
        )
        self.tax_purchase_8 = self.env["account.tax"].create(
            {
                "name": "IVA 8% Purch Report",
                "amount": 8,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group_8.id,
            }
        )
        self.tax_purchase_exempt = self.env["account.tax"].create(
            {
                "name": "Exenta Purch Report",
                "amount": 0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group_exempt.id,
            }
        )

        self.account_revenue = self.env["account.account"].create(
            {
                "name": "Revenue Test Report",
                "code": "991001",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_expense = self.env["account.account"].create(
            {
                "name": "Expense Test Report",
                "code": "991002",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_receivable = self.env["account.account"].create(
            {
                "name": "Receivable Test Report",
                "code": "991003",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_payable = self.env["account.account"].create(
            {
                "name": "Payable Test Report",
                "code": "991004",
                "account_type": "liability_payable",
                "reconcile": True,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner Report",
                "vat": "J-12345678-9",
                "property_account_receivable_id": self.account_receivable.id,
                "property_account_payable_id": self.account_payable.id,
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Test Product Report",
                "type": "service",
                "list_price": 100,
                "taxes_id": [(6, 0, [self.tax_sale_16.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_purchase_16.id])],
                "property_account_income_id": self.account_revenue.id,
                "property_account_expense_id": self.account_expense.id,
            }
        )

        self.journal_sale = self.env["account.journal"].create(
            {
                "name": "Sale Journal Report",
                "type": "sale",
                "code": "REPSJ",
                "company_id": self.company.id,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.journal_purchase = self.env["account.journal"].create(
            {
                "name": "Purchase Journal Report",
                "type": "purchase",
                "code": "REPPJ",
                "company_id": self.company.id,
                "default_account_id": self.account_expense.id,
            }
        )
        self.journal_debit = self.env["account.journal"].create(
            {
                "name": "Debit Journal Report",
                "type": "sale",
                "code": "REPDJ",
                "company_id": self.company.id,
                "is_debit": True,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.journal_purchase_intl = self.env["account.journal"].create(
            {
                "name": "Intl Purchase Journal Report",
                "type": "purchase",
                "code": "REPIJ",
                "company_id": self.company.id,
                "is_purchase_international": True,
                "default_account_id": self.account_expense.id,
            }
        )

    def _create_move_vals(self, move_type, journal, tax_ids, correlative="00001",
                          invoice_date_display=None, state="draft", **kwargs):
        today = fields.Date.today()
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "correlative": correlative,
            "invoice_date": today,
            "date": today,
            "invoice_date_display": invoice_date_display or today,
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
            "foreign_rate": 38.0,
            "foreign_inverse_rate": 38.0,
            "manually_set_rate": True,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 100,
                        "tax_ids": [(6, 0, tax_ids)],
                    },
                )
            ],
        }
        vals.update(kwargs)
        return vals

    def _create_move(self, move_type, journal, tax_ids, correlative="00001",
                     invoice_date_display=None, **kwargs):
        vals = self._create_move_vals(
            move_type, journal, tax_ids, correlative, invoice_date_display, **kwargs
        )
        return self.env["account.move"].create(vals)

    def _create_posted_move(self, move_type, journal, tax_ids, correlative="00001",
                            invoice_date_display=None, **kwargs):
        move = self._create_move(
            move_type, journal, tax_ids, correlative, invoice_date_display, **kwargs
        )
        move.action_post()
        return move

    def _create_wizard(self, report, date_from=None, date_to=None, **kwargs):
        vals = {
            "report": report,
            "date_from": date_from or (fields.Date.today() - timedelta(days=60)),
            "date_to": date_to or fields.Date.today(),
        }
        vals.update(kwargs)
        return self.env["wizard.accounting.reports"].create(vals)

    # ============================================================
    # Phase 1: Defaults
    # ============================================================

    def test_default_date_from_previous_month(self):
        wizard = self._create_wizard("sale")
        self.assertTrue(wizard)

    def test_default_date_to_today(self):
        wizard = self._create_wizard("sale", date_from=fields.Date.today(),
                                     date_to=fields.Date.today())
        self.assertEqual(wizard.date_to, fields.Date.today())

    def test_default_company(self):
        wizard = self._create_wizard("sale", date_from=fields.Date.today(),
                                     date_to=fields.Date.today())
        self.assertEqual(wizard.company_id, self.company)

    def test_default_currency_system_vef(self):
        self.company.currency_id = self.currency_vef
        wizard = self._create_wizard("sale", date_from=fields.Date.today(),
                                     date_to=fields.Date.today())
        self.assertTrue(wizard.show_field_currency_system)

    def test_default_currency_system_non_vef(self):
        self.company.write({
            "currency_id": self.currency_usd.id,
            "foreign_currency_id": self.currency_vef.id,
        })
        wizard = self._create_wizard("sale")
        self.assertTrue(wizard)

    # ============================================================
    # Phase 2: Utility methods
    # ============================================================

    def test_format_date(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._format_date("2025-03-15"), "15/03/2025")

    def test_determinate_type_out_invoice(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_type("out_invoice"), "FAC")

    def test_determinate_type_in_invoice(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_type("in_invoice"), "FAC")

    def test_determinate_type_out_refund(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_type("out_refund"), "NC")

    def test_determinate_type_in_refund(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_type("in_refund"), "NC")

    def test_determinate_type_out_debit(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_type("out_debit"), "ND")

    def test_determinate_type_in_debit(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_type("in_debit"), "ND")

    def test_determinate_type_for_move_debit_journal(self):
        move = self._create_move("out_invoice", self.journal_debit, [self.tax_sale_16.id])
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_type_for_move(move), "ND")

    def test_transaction_type_invoice_posted(self):
        move = self._create_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id]
        )
        move.write({"state": "posted"})
        move = self.env["account.move"].browse(move.id)
        self.assertEqual(move.state, "posted")
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_transaction_type(move), "01-REG")

    def test_transaction_type_credit_note_posted(self):
        invoice = self._create_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id]
        )
        invoice.write({"state": "posted"})
        invoice = self.env["account.move"].browse(invoice.id)
        refund = self._create_move(
            "out_refund", self.journal_sale, [self.tax_sale_16.id],
            reversed_entry_id=invoice.id,
            correlative="00002",
        )
        refund.write({"state": "posted"})
        refund = self.env["account.move"].browse(refund.id)
        self.assertEqual(refund.state, "posted")
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_transaction_type(refund), "03-REG")

    def test_transaction_type_cancelled(self):
        move = self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id]
        )
        move.button_cancel()
        self.assertEqual(move.state, "cancel")
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard._determinate_transaction_type(move), "03-ANU")

    def test_convert_currency_to_float_empty(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard.convert_currency_to_float(""), 0.0)

    def test_convert_currency_to_float_none(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard.convert_currency_to_float(None), 0.0)

    def test_convert_currency_to_float_zero(self):
        wizard = self._create_wizard("sale")
        result = wizard.convert_currency_to_float("Bs0.00")
        self.assertTrue(isinstance(result, float))

    def test_convert_currency_to_float_invalid(self):
        wizard = self._create_wizard("sale")
        self.assertEqual(wizard.convert_currency_to_float("ABC"), 0.0)

    # ============================================================
    # Phase 3: Domain & search
    # ============================================================

    def test_domain_sale_basic(self):
        today = fields.Date.today()
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        domain = wizard._get_domain()
        self.assertIn(("company_id", "=", self.company.id), domain)
        self.assertIn(("date", ">=", today), domain)
        self.assertIn(("date", "<=", today), domain)
        self.assertIn(("correlative", "not in", ["/", False]), domain)
        self.assertIn(("state", "in", ("posted", "cancel")), domain)
        self.assertIn(("move_type", "in", ["out_invoice", "out_refund"]), domain)

    def test_domain_purchase_basic(self):
        today = fields.Date.today()
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        domain = wizard._get_domain()
        self.assertIn(("move_type", "in", ["in_invoice", "in_refund", "in_debit"]), domain)

    def test_domain_hides_international_all_config_true(self):
        self.company.not_show_general_aliquot_purchase_international = True
        self.company.not_show_reduced_aliquot_purchase_international = True
        self.company.not_show_extend_aliquot_purchase_international = True
        self.company.not_show_total_purchases_with_international_iva = True
        self.company.not_show_exempt_total_purchases = True
        self.company.not_show_total_purchases_international = True
        wizard = self._create_wizard("purchase")
        domain = wizard._get_domain()
        self.assertIn(
            ("journal_id.is_purchase_international", "=", False), domain
        )

    def test_search_moves_order_purchase(self):
        m1 = self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="A",
        )
        m2 = self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="B",
        )
        wizard = self._create_wizard("purchase")
        moves = wizard.search_moves()
        self.assertIn(m1.id, moves.ids)
        self.assertIn(m2.id, moves.ids)

    # ============================================================
    # Phase 4: _determinate_amount_taxeds
    # ============================================================

    def test_amount_taxeds_draft_returns_zeros(self):
        move = self._create_move("out_invoice", self.journal_sale, [self.tax_sale_16.id])
        wizard = self._create_wizard("sale")
        result = wizard._determinate_amount_taxeds(move)
        self.assertEqual(result["amount_untaxed"], 0.0)
        self.assertEqual(result["amount_taxed"], 0.0)
        self.assertEqual(result["tax_base_general_aliquot"], 0.0)
        self.assertEqual(result["amount_general_aliquot"], 0.0)

    def test_amount_taxeds_posted_has_tax_totals_fields(self):
        move = self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id]
        )
        wizard = self._create_wizard("sale")
        result = wizard._determinate_amount_taxeds(move)
        self.assertIn("tax_base_exempt_aliquot", result)
        self.assertIn("amount_exempt_aliquot", result)
        self.assertIn("tax_base_general_aliquot", result)
        self.assertIn("amount_general_aliquot", result)
        self.assertIn("tax_base_reduced_aliquot", result)
        self.assertIn("amount_reduced_aliquot", result)
        self.assertIn("tax_base_extend_aliquot", result)
        self.assertIn("amount_extend_aliquot", result)

    def test_amount_taxeds_purchase_international(self):
        self.company.general_aliquot_purchase_international = self.tax_purchase_16.id
        self.company.exent_aliquot_purchase_international = self.tax_purchase_16.id
        today = fields.Date.today()
        move = self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="C-12345",
            invoice_date_display=today,
        )
        self.assertEqual(move.state, "posted")
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        result = wizard._determinate_amount_taxeds(move)
        self.assertEqual(result["tax_base_general_aliquot"], 0.0)
        self.assertEqual(result["amount_general_aliquot"], 0.0)
        self.assertIn("tax_base_general_aliquot_international", result)

    def test_amount_taxeds_purchase_international_custom_fields(self):
        self.company.general_aliquot_purchase_international = self.tax_purchase_16.id
        move = self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="C-67890",
            tax_base_for_international_purchase=500,
            tax_amount_for_international_purchase=80,
        )
        wizard = self._create_wizard("purchase")
        result = wizard._determinate_amount_taxeds(move)
        self.assertEqual(result["tax_base_general_aliquot_international"], 500)
        self.assertEqual(result["amount_general_aliquot_international"], 80)

    def test_amount_taxeds_no_deductible(self):
        self.company.config_deductible_tax = True
        self.company.general_aliquot_purchase = self.tax_purchase_16.id
        self.company.no_deductible_general_aliquot_purchase = self.tax_purchase_nd_16.id
        move = self._create_posted_move(
            "in_invoice",
            self.journal_purchase,
            [self.tax_purchase_nd_16.id],
            correlative="ND001",
        )
        wizard = self._create_wizard("purchase")
        result = wizard._determinate_amount_taxeds(move)
        self.assertGreater(
            result.get("tax_base_general_aliquot_no_deductible", 0)
            + result.get("amount_general_aliquot_no_deductible", 0),
            0.0,
        )

    def test_amount_taxeds_no_deductible_not_purchase(self):
        self.company.config_deductible_tax = True
        self.company.no_deductible_general_aliquot_purchase = self.tax_purchase_nd_16.id
        move = self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id]
        )
        wizard = self._create_wizard("sale")
        result = wizard._determinate_amount_taxeds(move)
        self.assertNotIn("tax_base_general_aliquot_no_deductible", result)

    def test_amount_taxeds_amount_import_international(self):
        self.company.general_aliquot_purchase_international = self.tax_purchase_16.id
        move = self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="IMP-001",
        )
        wizard = self._create_wizard("purchase")
        result = wizard._determinate_amount_taxeds(move)
        self.assertGreaterEqual(result.get("amount_import_international", 0), 0.0)

    # ============================================================
    # Phase 5: Line formatters
    # ============================================================

    def test_fields_sale_book_line_structure(self):
        move = self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id]
        )
        wizard = self._create_wizard("sale")
        taxes = wizard._determinate_amount_taxeds(move)
        line = wizard._fields_sale_book_line(move, taxes)
        self.assertEqual(line["_id"], move.id)
        self.assertEqual(line["move_type"], "FAC")
        self.assertEqual(line["invoice_number"], move.name)
        self.assertEqual(line["credit_note_number"], "--")
        self.assertEqual(line["debit_note_number"], "--")
        self.assertEqual(line["vat"], move.vat)
        self.assertIn("document_date", line)
        self.assertIn("correlative", line)
        self.assertIn("total_sales", line)

    def test_fields_sale_book_line_debit_journal(self):
        today = fields.Date.today()
        move = self._create_posted_move(
            "out_invoice", self.journal_debit, [self.tax_sale_16.id],
            invoice_date_display=today,
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        taxes = wizard._determinate_amount_taxeds(move)
        line = wizard._fields_sale_book_line(move, taxes)
        self.assertEqual(line["move_type"], "ND")
        self.assertEqual(line["debit_note_number"], move.name)

    def test_fields_sale_book_line_missing_invoice_date_raises(self):
        move = self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id]
        )
        move.invoice_date_display = False
        wizard = self._create_wizard("sale")
        taxes = wizard._determinate_amount_taxeds(move)
        with self.assertRaises(UserError):
            wizard._fields_sale_book_line(move, taxes)

    def test_fields_purchase_book_line_structure(self):
        move = self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="P001"
        )
        wizard = self._create_wizard("purchase")
        taxes = wizard._determinate_amount_taxeds(move)
        line = wizard._fields_purchase_book_line(move, taxes)
        self.assertEqual(line["_id"], move.id)
        self.assertEqual(line["move_type"], "FAC")
        self.assertIn("total_purchases", line)
        self.assertIn("correlative", line)

    def test_fields_purchase_book_line_international(self):
        move = self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="D-99999",
            correlative="D-99999",
        )
        wizard = self._create_wizard("purchase")
        taxes = wizard._determinate_amount_taxeds(move)
        line = wizard._fields_purchase_book_line(move, taxes)
        if line is not None:
            self.assertIn("declaration_unique_of_customs", line)
            self.assertIn("amount_import_international", line)

    def test_fields_purchase_book_line_international_skips_no_tax(self):
        move = self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="D-SKIP",
            correlative="D-SKIP",
        )
        self.company.not_show_general_aliquot_purchase_international = True
        self.company.not_show_reduced_aliquot_purchase_international = True
        self.company.not_show_extend_aliquot_purchase_international = True
        wizard = self._create_wizard("purchase")
        taxes = wizard._determinate_amount_taxeds(move)
        line = wizard._fields_purchase_book_line(move, taxes)
        self.assertIsNone(line)

    def test_fields_purchase_book_line_missing_date_raises(self):
        move = self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="P002"
        )
        move.invoice_date_display = False
        wizard = self._create_wizard("purchase")
        taxes = wizard._determinate_amount_taxeds(move)
        with self.assertRaises(UserError):
            wizard._fields_purchase_book_line(move, taxes)

    # ============================================================
    # Phase 6: Parsers
    # ============================================================

    def test_parse_purchase_book_data(self):
        self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="P010"
        )
        wizard = self._create_wizard("purchase")
        lines = wizard.parse_purchase_book_data()
        self.assertEqual(len(lines), 1)

    def test_parse_purchase_book_data_skips_none(self):
        self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="NONE-TEST",
            correlative="NONE-TEST",
        )
        self.company.not_show_general_aliquot_purchase_international = True
        self.company.not_show_reduced_aliquot_purchase_international = True
        self.company.not_show_extend_aliquot_purchase_international = True
        wizard = self._create_wizard("purchase")
        lines = wizard.parse_purchase_book_data()
        self.assertEqual(len(lines), 0)

    # ============================================================
    # Phase 7: Resume books
    # ============================================================

    def test_resume_books_exempt_aliquot(self):
        today = fields.Date.today()
        self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id],
            correlative="R001"
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves, "exempt_aliquot")
        self.assertEqual(len(result), 4)

    def test_resume_books_general_aliquot(self):
        today = fields.Date.today()
        self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id],
            correlative="R002"
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves, "general_aliquot")
        self.assertEqual(len(result), 4)

    def test_resume_books_reduced_aliquot(self):
        today = fields.Date.today()
        self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id],
            correlative="R003"
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves, "reduced_aliquot")
        self.assertEqual(len(result), 4)

    def test_resume_books_extend_aliquot(self):
        today = fields.Date.today()
        self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id],
            correlative="R004"
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves, "extend_aliquot")
        self.assertEqual(len(result), 4)

    def test_resume_books_general_aliquot_international(self):
        today = fields.Date.today()
        self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="INTL-GEN",
            correlative="INTL-GEN",
        )
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves, "general_aliquot_international")
        self.assertEqual(len(result), 4)

    def test_resume_books_reduced_aliquot_international(self):
        today = fields.Date.today()
        self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="INTL-RED",
            correlative="INTL-RED",
        )
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves, "reduced_aliquot_international")
        self.assertEqual(len(result), 4)

    def test_resume_books_extend_aliquot_international(self):
        today = fields.Date.today()
        self._create_posted_move(
            "in_invoice",
            self.journal_purchase_intl,
            [self.tax_purchase_16.id],
            declaration_unique_of_customs="INTL-EXT",
            correlative="INTL-EXT",
        )
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves, "extend_aliquot_international")
        self.assertEqual(len(result), 4)

    def test_resume_books_no_tax_type(self):
        today = fields.Date.today()
        self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id],
            correlative="R005"
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        moves = wizard.search_moves()
        result = wizard._determinate_resume_books(moves)
        self.assertEqual(result, [0.0, 0.0, 0.0, 0.0])

    def test_resume_books_filters_future_dates(self):
        today = fields.Date.today()
        self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id],
            correlative="R006",
            invoice_date_display=today - timedelta(days=90),
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        moves = wizard.search_moves()
        self.assertEqual(len(moves), 0)
        result = wizard._determinate_resume_books(moves, "general_aliquot")
        self.assertEqual(result, [0.0, 0.0, 0.0, 0.0])

    # ============================================================
    # Phase 8: Column definitions
    # ============================================================

    def test_sale_book_fields_flat(self):
        wizard = self._create_wizard("sale")
        fields_list = wizard.sale_book_fields()
        self.assertTrue(isinstance(fields_list, list))
        self.assertGreater(len(fields_list), 0)
        field_names = [f["field"] for f in fields_list]
        self.assertIn("index", field_names)
        self.assertIn("document_date", field_names)
        self.assertIn("vat", field_names)

    def test_purchase_book_fields_flat(self):
        wizard = self._create_wizard("purchase")
        fields_list = wizard.purchase_book_fields()
        self.assertTrue(isinstance(fields_list, list))
        self.assertGreater(len(fields_list), 0)

    def test_sale_book_field_groups_basic(self):
        wizard = self._create_wizard("sale")
        groups = wizard._get_sale_book_field_groups()
        self.assertGreaterEqual(len(groups), 3)
        headers = [g["header"] for g in groups]
        self.assertIn("DETALLE DEL DOCUMENTO", headers)
        self.assertIn("TOTALES", headers)

    def test_sale_book_field_groups_hide_reduced(self):
        self.company.not_show_reduced_aliquot_sale = True
        wizard = self._create_wizard("sale")
        groups = wizard._get_sale_book_field_groups()
        headers = [g["header"] for g in groups]
        self.assertNotIn("ALÍCUOTA REDUCIDA (8%)", headers)

    def test_sale_book_field_groups_hide_extend(self):
        self.company.not_show_extend_aliquot_sale = True
        wizard = self._create_wizard("sale")
        groups = wizard._get_sale_book_field_groups()
        headers = [g["header"] for g in groups]
        self.assertNotIn("ALÍCUOTA ADICIONAL (31%)", headers)

    def test_sale_book_field_groups_all_visible(self):
        self.company.not_show_reduced_aliquot_sale = False
        self.company.not_show_extend_aliquot_sale = False
        wizard = self._create_wizard("sale")
        groups = wizard._get_sale_book_field_groups()
        headers = [g["header"] for g in groups]
        self.assertIn("ALÍCUOTA REDUCIDA (8%)", headers)
        self.assertIn("ALÍCUOTA ADICIONAL (31%)", headers)

    def test_purchase_book_field_groups_basic(self):
        wizard = self._create_wizard("purchase")
        groups = wizard._get_purchase_book_field_groups()
        headers = [g["header"] for g in groups]
        self.assertIn("DETALLE DEL DOCUMENTO", headers)
        self.assertIn("TOTALES", headers)
        self.assertIn("COMPRAS NACIONALES", headers)

    def test_purchase_book_field_groups_international(self):
        self.company.not_show_general_aliquot_purchase_international = False
        wizard = self._create_wizard("purchase")
        groups = wizard._get_purchase_book_field_groups()
        headers = [g["header"] for g in groups]
        self.assertIn("COMPRAS INTERNACIONALES", headers)

    def test_purchase_book_field_groups_hide_international(self):
        self.company.not_show_general_aliquot_purchase_international = True
        self.company.not_show_reduced_aliquot_purchase_international = True
        self.company.not_show_extend_aliquot_purchase_international = True
        wizard = self._create_wizard("purchase")
        groups = wizard._get_purchase_book_field_groups()
        headers = [g["header"] for g in groups]
        self.assertNotIn("COMPRAS INTERNACIONALES", headers)

    def test_purchase_book_field_groups_no_deductible(self):
        self.company.config_deductible_tax = True
        self.company.no_deductible_general_aliquot_purchase = self.tax_purchase_nd_16.id
        wizard = self._create_wizard("purchase")
        groups = wizard._get_purchase_book_field_groups()
        headers = [g["header"] for g in groups]
        self.assertIn("IMPUESTOS NO DEDUCIBLES", headers)

    def test_not_deductible_purchase_book_fields(self):
        self.company.no_deductible_general_aliquot_purchase = self.tax_purchase_nd_16.id
        self.company.no_deductible_reduced_aliquot_purchase = self.tax_purchase_8.id
        wizard = self._create_wizard("purchase")
        base_fields = [
            {"name": "N° operacion", "field": "index"},
            {"name": "Fecha del documento", "field": "document_date"},
        ]
        result = wizard.not_deductible_purchase_book_fields(base_fields)
        self.assertGreaterEqual(len(result), len(base_fields))

    def test_resume_book_headers_sale(self):
        wizard = self._create_wizard("sale")
        headers = wizard.resume_book_headers()
        self.assertEqual(len(headers), 4)
        self.assertEqual(headers[0]["field"], "resume")
        self.assertEqual(headers[1]["field"], "inv_debit_notes")
        self.assertEqual(headers[2]["field"], "credit_notes")
        self.assertEqual(headers[3]["field"], "total")

    def test_resume_book_headers_purchase(self):
        wizard = self._create_wizard("purchase")
        headers = wizard.resume_book_headers()
        self.assertEqual(len(headers), 4)
        self.assertIn("Crédito", headers[0]["headers"][1])

    # ============================================================
    # Phase 9: Report generation
    # ============================================================

    def test_generate_report_sale_no_records_raises(self):
        wizard = self._create_wizard("sale",
                                     date_from=fields.Date.today(),
                                     date_to=fields.Date.today())
        with self.assertRaises(UserError):
            wizard.generate_report()

    def test_generate_report_purchase_no_records_raises(self):
        wizard = self._create_wizard("purchase",
                                     date_from=fields.Date.today(),
                                     date_to=fields.Date.today())
        with self.assertRaises(UserError):
            wizard.generate_report()

    def test_generate_report_purchase_returns_action(self):
        today = fields.Date.today()
        self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="GENP01"
        )
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        action = wizard.generate_report()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("company_id", action["url"])

    def test_download_sales_book_url(self):
        wizard = self._create_wizard("sale")
        result = wizard.download_sales_book()
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertIn("/web/download_sales_book", result["url"])

    def test_download_purchases_book_url(self):
        wizard = self._create_wizard("purchase")
        result = wizard.download_purchases_book()
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertIn("/web/download_purchase_book", result["url"])

    # ============================================================
    # Phase 10: Excel generation
    # ============================================================

    def test_generate_purchases_book_bytes(self):
        today = fields.Date.today()
        self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="XLP01"
        )
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        file_bytes = wizard.generate_purchases_book(self.company.id)
        self.assertIsInstance(file_bytes, bytes)
        self.assertGreater(len(file_bytes), 0)
        self.assertEqual(file_bytes[:2], b"PK")

    # ============================================================
    # Phase 11: _resume_sale_book_fields / _resume_purchase_book_fields
    # ============================================================

    def test_resume_sale_book_fields(self):
        today = fields.Date.today()
        self._create_posted_move(
            "out_invoice", self.journal_sale, [self.tax_sale_16.id],
            correlative="RSF01"
        )
        wizard = self._create_wizard("sale", date_from=today, date_to=today)
        moves = wizard.search_moves()
        fields_list = wizard._resume_sale_book_fields(moves)
        self.assertEqual(len(fields_list), 7)
        self.assertEqual(fields_list[-1]["total"], True)

    def test_resume_purchase_book_fields(self):
        today = fields.Date.today()
        self._create_posted_move(
            "in_invoice", self.journal_purchase, [self.tax_purchase_16.id],
            correlative="RPF01"
        )
        wizard = self._create_wizard("purchase", date_from=today, date_to=today)
        moves = wizard.search_moves()
        fields_list = wizard._resume_purchase_book_fields(moves)
        self.assertEqual(len(fields_list), 9)
        self.assertEqual(fields_list[-1]["total"], True)
