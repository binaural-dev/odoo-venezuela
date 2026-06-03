from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountingReports(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.wizard_model = self.env["wizard.accounting.reports"]
        self.move_model = self.env["account.move"]
        self.journal_model = self.env["account.journal"]

        self.partner = self.env["res.partner"].create(
            {
                "name": "Proveedor Prueba",
                "vat": "J-12345678-9",
            }
        )

        self.purchase_journal = self._create_purchase_journal("PB001", is_debit=False)
        self.debit_purchase_journal = self._create_purchase_journal("PB002", is_debit=True)
        self.sale_journal = self._create_sale_journal("SV001")

        self.wizard = self.wizard_model.create(
            {
                "report": "purchase",
                "date_from": "2023-01-01",
                "date_to": "2023-01-31",
                "company_id": self.company.id,
            }
        )

        self.sample_taxes = {
            "amount_untaxed": 100.0,
            "amount_taxed": 150.0,
            "tax_base_exempt_aliquot": 50.0,
            "amount_exempt_aliquot": 0.0,
            "amount_reduced_aliquot": 8.0,
            "amount_general_aliquot": 16.0,
            "amount_extend_aliquot": 31.0,
            "tax_base_reduced_aliquot": 100.0,
            "tax_base_general_aliquot": 200.0,
            "tax_base_extend_aliquot": 300.0,
            "national_amount_taxed": 120.0,
            "national_tax_base_exempt_aliquot": 20.0,
            "international_amount_taxed": 30.0,
            "international_tax_base_exempt_aliquot": 10.0,
            "amount_reduced_aliquot_international": 2.4,
            "amount_general_aliquot_international": 4.8,
            "amount_extend_aliquot_international": 9.3,
            "tax_base_reduced_aliquot_international": 30.0,
            "tax_base_general_aliquot_international": 60.0,
            "tax_base_extend_aliquot_international": 90.0,
            "amount_import_international": 106.5,
            "amount_reduced_aliquot_no_deductible": 1.6,
            "amount_general_aliquot_no_deductible": 3.2,
            "amount_extend_aliquot_no_deductible": 6.2,
            "tax_base_reduced_aliquot_no_deductible": 20.0,
            "tax_base_general_aliquot_no_deductible": 40.0,
            "tax_base_extend_aliquot_no_deductible": 60.0,
        }

    def _create_purchase_journal(self, code, is_debit=False):
        vals = {
            "name": "Purchase Journal %s" % code,
            "code": code,
            "type": "purchase",
            "company_id": self.company.id,
        }
        if "is_debit" in self.journal_model._fields:
            vals["is_debit"] = is_debit
        return self.journal_model.create(vals)

    def _create_sale_journal(self, code):
        return self.journal_model.create(
            {
                "name": "Sale Journal %s" % code,
                "code": code,
                "type": "sale",
                "company_id": self.company.id,
            }
        )

    def _create_move(
        self,
        name,
        move_type="in_invoice",
        journal=None,
        invoice_date=date(2023, 1, 10),
        accounting_date=date(2023, 1, 10),
        state="posted",
        correlative="CTRL-001",
        reversed_entry=None,
        debit_origin=None,
        declaration_unique_of_customs=None,
    ):
        journal = journal or self.purchase_journal
        vals = {
            "partner_id": self.partner.id,
            "move_type": move_type,
            "date": accounting_date,
            "journal_id": journal.id,
            "company_id": self.company.id,
            "currency_id": self.company.currency_id.id,
        }

        if "invoice_date" in self.move_model._fields:
            vals["invoice_date"] = invoice_date

        if "correlative" in self.move_model._fields:
            vals["correlative"] = correlative

        if reversed_entry and "reversed_entry_id" in self.move_model._fields:
            vals["reversed_entry_id"] = reversed_entry.id

        if debit_origin and "debit_origin_id" in self.move_model._fields:
            vals["debit_origin_id"] = debit_origin.id

        if (
            declaration_unique_of_customs is not None
            and "declaration_unique_of_customs" in self.move_model._fields
        ):
            vals["declaration_unique_of_customs"] = declaration_unique_of_customs

        move = self.move_model.create(vals)
        move.with_context(check_move_validity=False).write(
            {
                "name": name,
                "state": state,
            }
        )
        return move

    def _write_company_flags(self, **vals):
        vals = {key: value for key, value in vals.items() if key in self.company._fields}
        if vals:
            self.company.write(vals)

    def _create_tax(self, name, amount, type_tax_use="purchase"):
        group = self.env["account.tax.group"].create({"name": name})
        return self.env["account.tax"].create(
            {
                "name": name,
                "amount_type": "percent",
                "amount": amount,
                "type_tax_use": type_tax_use,
                "tax_group_id": group.id,
                "company_id": self.company.id,
            }
        )

    def _setup_company_tax_configuration(self):
        if getattr(self, "_company_tax_configured", False):
            return

        sale_exempt = self._create_tax("Sale Exempt", 0, "sale")
        sale_reduced = self._create_tax("Sale Reduced", 8, "sale")
        sale_general = self._create_tax("Sale General", 16, "sale")
        sale_extend = self._create_tax("Sale Extend", 31, "sale")

        purchase_exempt = self._create_tax("Purchase Exempt", 0, "purchase")
        purchase_reduced = self._create_tax("Purchase Reduced", 8, "purchase")
        purchase_general = self._create_tax("Purchase General", 16, "purchase")
        purchase_extend = self._create_tax("Purchase Extend", 31, "purchase")

        purchase_exempt_int = self._create_tax("Purchase Exempt Int", 0, "purchase")
        purchase_reduced_int = self._create_tax("Purchase Reduced Int", 8, "purchase")
        purchase_general_int = self._create_tax("Purchase General Int", 16, "purchase")
        purchase_extend_int = self._create_tax("Purchase Extend Int", 31, "purchase")

        no_deduct_general = self._create_tax("No Deductible General", 16, "purchase")
        no_deduct_reduced = self._create_tax("No Deductible Reduced", 8, "purchase")
        no_deduct_extend = self._create_tax("No Deductible Extend", 31, "purchase")

        self._write_company_flags(
            exent_aliquot_sale=sale_exempt.id,
            reduced_aliquot_sale=sale_reduced.id,
            general_aliquot_sale=sale_general.id,
            extend_aliquot_sale=sale_extend.id,
            exent_aliquot_purchase=purchase_exempt.id,
            reduced_aliquot_purchase=purchase_reduced.id,
            general_aliquot_purchase=purchase_general.id,
            extend_aliquot_purchase=purchase_extend.id,
            exent_aliquot_purchase_international=purchase_exempt_int.id,
            reduced_aliquot_purchase_international=purchase_reduced_int.id,
            general_aliquot_purchase_international=purchase_general_int.id,
            extend_aliquot_purchase_international=purchase_extend_int.id,
            no_deductible_general_aliquot_purchase=no_deduct_general.id,
            no_deductible_reduced_aliquot_purchase=no_deduct_reduced.id,
            no_deductible_extend_aliquot_purchase=no_deduct_extend.id,
            config_deductible_tax=True,
            not_show_reduced_aliquot_sale=False,
            not_show_extend_aliquot_sale=False,
            not_show_reduced_aliquot_purchase=False,
            not_show_extend_aliquot_purchase=False,
            not_show_general_aliquot_purchase_international=False,
            not_show_reduced_aliquot_purchase_international=False,
            not_show_extend_aliquot_purchase_international=False,
            not_show_total_purchases_national=False,
            not_show_total_purchases_with_iva=False,
            not_show_national_exempt_total_purchases=False,
            not_show_total_purchases_international=False,
            not_show_total_purchases_with_international_iva=False,
            not_show_exempt_total_purchases=False,
        )

        self._company_tax_configured = True

    def _fake_journal(self, **vals):
        data = {
            "is_debit": False,
            "is_purchase_international": False,
            "is_sale_international": False,
        }
        data.update(vals)
        return SimpleNamespace(**data)

    def _fake_move(self, **vals):
        data = {
            "id": 999,
            "invoice_date": date(2023, 1, 10),
            "date": date(2023, 1, 10),
            "vat": "J-12345678-9",
            "invoice_partner_display_name": "Partner Demo",
            "name": "MOVE/2023/0001",
            "move_type": "in_invoice",
            "state": "posted",
            "journal_id": self._fake_journal(),
            "debit_origin_id": SimpleNamespace(name="DEBIT/ORIGIN"),
            "reversed_entry_id": SimpleNamespace(name=False),
            "correlative": "CTRL-001",
            "declaration_unique_of_customs": False,
            "tax_totals": {},
            "tax_base_for_international_purchase": 0.0,
            "tax_amount_for_international_purchase": 0.0,
        }
        data.update(vals)
        return SimpleNamespace(**data)

    def test_format_date(self):
        self.assertEqual(self.wizard._format_date(date(2023, 1, 10)), "10/01/2023")

    def test_determinate_type_for_move_regular_purchase(self):
        move = self._create_move(
            name="BILL/2023/0001",
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        self.assertEqual(self.wizard._determinate_type_for_move(move), "FAC")

    def test_determinate_type_for_move_debit_purchase(self):
        origin_move = self._create_move(
            name="BILL/2023/ORIGIN",
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        move = self._create_move(
            name="DEBIT/2023/0001",
            move_type="in_invoice",
            journal=self.debit_purchase_journal,
            debit_origin=origin_move,
        )
        self.assertEqual(self.wizard._determinate_type_for_move(move), "ND")

    def test_determinate_type_for_move_purchase_refund(self):
        origin_move = self._create_move(
            name="BILL/2023/0002",
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        move = self._create_move(
            name="REF/2023/0001",
            move_type="in_refund",
            journal=self.purchase_journal,
            reversed_entry=origin_move,
        )
        self.assertEqual(self.wizard._determinate_type_for_move(move), "NC")

    def test_determinate_transaction_type_regular_purchase(self):
        move = self._create_move(
            name="BILL/2023/0003",
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        self.assertEqual(self.wizard._determinate_transaction_type(move), "01-REG")

    def test_determinate_transaction_type_debit_purchase(self):
        origin_move = self._create_move(
            name="BILL/2023/ORIGIN2",
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        move = self._create_move(
            name="DEBIT/2023/0002",
            move_type="in_invoice",
            journal=self.debit_purchase_journal,
            debit_origin=origin_move,
        )
        self.assertEqual(self.wizard._determinate_transaction_type(move), "02-REG")

    def test_determinate_transaction_type_purchase_refund(self):
        origin_move = self._create_move(
            name="BILL/2023/0004",
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        move = self._create_move(
            name="REF/2023/0002",
            move_type="in_refund",
            journal=self.purchase_journal,
            reversed_entry=origin_move,
        )
        self.assertEqual(self.wizard._determinate_transaction_type(move), "03-REG")

    def test_fields_purchase_book_line_regular_invoice(self):
        move = self._create_move(
            name="BILL/2023/0005",
            move_type="in_invoice",
            journal=self.purchase_journal,
            correlative="CTRL-REG-001",
        )

        line = self.wizard._fields_purchase_book_line(move, dict(self.sample_taxes))

        self.assertEqual(line["_id"], move.id)
        self.assertEqual(line["document_date"], "10/01/2023")
        self.assertEqual(line["accounting_date"], "10/01/2023")
        self.assertEqual(line["vat"], move.vat)
        self.assertEqual(line["partner_name"], move.invoice_partner_display_name)
        self.assertEqual(line["document_number"], "BILL/2023/0005")
        self.assertEqual(line["move_type"], "FAC")
        self.assertEqual(line["transaction_type"], "01-REG")
        self.assertEqual(line["number_invoice_affected"], "--")
        self.assertEqual(line["correlative"], "CTRL-REG-001")

        self.assertEqual(line["reduced_aliquot"], 0.08)
        self.assertEqual(line["general_aliquot"], 0.16)
        self.assertEqual(line["extend_aliquot"], 0.31)

        self.assertEqual(line["total_purchases"], 150.0)
        self.assertEqual(line["total_purchases_iva"], 100.0)
        self.assertEqual(line["total_purchases_not_iva"], 50.0)
        self.assertEqual(line["amount_reduced_aliquot"], 8.0)
        self.assertEqual(line["amount_general_aliquot"], 16.0)
        self.assertEqual(line["amount_extend_aliquot"], 31.0)
        self.assertEqual(line["tax_base_reduced_aliquot"], 100.0)
        self.assertEqual(line["tax_base_general_aliquot"], 200.0)
        self.assertEqual(line["tax_base_extend_aliquot"], 300.0)

        self.assertEqual(line["total_purchases_national"], 120.0)
        self.assertEqual(line["total_purchases_iva_national"], 100.0)
        self.assertEqual(line["total_purchases_not_iva_national"], 20.0)
        self.assertEqual(line["total_purchases_international"], 30.0)
        self.assertEqual(line["total_purchases_iva_international"], 20.0)
        self.assertEqual(line["total_purchases_not_iva_international"], 10.0)
        self.assertEqual(line["amount_reduced_aliquot_international"], 2.4)
        self.assertEqual(line["amount_general_aliquot_international"], 4.8)
        self.assertEqual(line["amount_extend_aliquot_international"], 9.3)
        self.assertEqual(line["tax_base_reduced_aliquot_international"], 30.0)
        self.assertEqual(line["tax_base_general_aliquot_international"], 60.0)
        self.assertEqual(line["tax_base_extend_aliquot_international"], 90.0)
        self.assertEqual(line["declaration_unique_of_customs"], "-")
        self.assertEqual(line["amount_import_international"], 106.5)

        self.assertEqual(line["reduced_aliquot_no_deductible"], 0.08)
        self.assertEqual(line["general_aliquot_no_deductible"], 0.16)
        self.assertEqual(line["extend_aliquot_no_deductible"], 0.31)
        self.assertEqual(line["amount_reduced_aliquot_no_deductible"], 1.6)
        self.assertEqual(line["amount_general_aliquot_no_deductible"], 3.2)
        self.assertEqual(line["amount_extend_aliquot_no_deductible"], 6.2)
        self.assertEqual(line["tax_base_reduced_aliquot_no_deductible"], 20.0)
        self.assertEqual(line["tax_base_general_aliquot_no_deductible"], 40.0)
        self.assertEqual(line["tax_base_extend_aliquot_no_deductible"], 60.0)

    def test_fields_purchase_book_line_debit_journal_uses_debit_origin(self):
        origin_move = self._create_move(
            name="BILL/2023/ORIGIN3",
            move_type="in_invoice",
            journal=self.purchase_journal,
            correlative="CTRL-ORIGIN",
        )
        debit_move = self._create_move(
            name="DEBIT/2023/0003",
            move_type="in_invoice",
            journal=self.debit_purchase_journal,
            correlative="CTRL-DEBIT",
            debit_origin=origin_move,
        )

        line = self.wizard._fields_purchase_book_line(debit_move, dict(self.sample_taxes))

        self.assertEqual(line["move_type"], "ND")
        self.assertEqual(line["transaction_type"], "02-REG")
        self.assertEqual(line["number_invoice_affected"], origin_move.name)
        self.assertEqual(line["document_number"], "DEBIT/2023/0003")
        self.assertEqual(line["correlative"], "CTRL-DEBIT")

    def test_fields_purchase_book_line_refund_applies_negative_multiplier(self):
        original_move = self._create_move(
            name="BILL/2023/0006",
            move_type="in_invoice",
            journal=self.purchase_journal,
            correlative="CTRL-BASE-002",
        )
        refund_move = self._create_move(
            name="REF/2023/0004",
            move_type="in_refund",
            journal=self.purchase_journal,
            correlative="CTRL-REF-001",
            reversed_entry=original_move,
            declaration_unique_of_customs="DUA-0001",
        )

        line = self.wizard._fields_purchase_book_line(refund_move, dict(self.sample_taxes))

        self.assertEqual(line["move_type"], "NC")
        self.assertEqual(line["transaction_type"], "03-REG")
        self.assertEqual(line["number_invoice_affected"], original_move.name)
        self.assertEqual(line["correlative"], "-")
        self.assertEqual(line["declaration_unique_of_customs"], "DUA-0001")

        self.assertEqual(line["total_purchases"], 150.0)
        self.assertEqual(line["total_purchases_iva"], 200.0)
        self.assertEqual(line["total_purchases_not_iva"], -50.0)

        self.assertEqual(line["amount_reduced_aliquot"], -8.0)
        self.assertEqual(line["amount_general_aliquot"], -16.0)
        self.assertEqual(line["amount_extend_aliquot"], -31.0)
        self.assertEqual(line["tax_base_reduced_aliquot"], -100.0)
        self.assertEqual(line["tax_base_general_aliquot"], -200.0)
        self.assertEqual(line["tax_base_extend_aliquot"], -300.0)

        self.assertEqual(line["total_purchases_national"], 120.0)
        self.assertEqual(line["total_purchases_iva_national"], 140.0)
        self.assertEqual(line["total_purchases_not_iva_national"], -20.0)
        self.assertEqual(line["total_purchases_international"], 30.0)
        self.assertEqual(line["total_purchases_iva_international"], 40.0)
        self.assertEqual(line["total_purchases_not_iva_international"], -10.0)

        self.assertEqual(line["amount_reduced_aliquot_international"], -2.4)
        self.assertEqual(line["amount_general_aliquot_international"], -4.8)
        self.assertEqual(line["amount_extend_aliquot_international"], -9.3)
        self.assertEqual(line["tax_base_reduced_aliquot_international"], -30.0)
        self.assertEqual(line["tax_base_general_aliquot_international"], -60.0)
        self.assertEqual(line["tax_base_extend_aliquot_international"], -90.0)

        self.assertEqual(line["amount_reduced_aliquot_no_deductible"], -1.6)
        self.assertEqual(line["amount_general_aliquot_no_deductible"], -3.2)
        self.assertEqual(line["amount_extend_aliquot_no_deductible"], -6.2)
        self.assertEqual(line["tax_base_reduced_aliquot_no_deductible"], -20.0)
        self.assertEqual(line["tax_base_general_aliquot_no_deductible"], -40.0)
        self.assertEqual(line["tax_base_extend_aliquot_no_deductible"], -60.0)

    def test_fields_purchase_book_line_raises_if_posted_without_invoice_date(self):
        move = self._create_move(
            name="BILL/2023/NO-DATE",
            move_type="in_invoice",
            journal=self.purchase_journal,
            invoice_date=False,
            correlative="CTRL-NO-DATE",
        )

        with self.assertRaisesRegex(UserError, "invoice date"):
            self.wizard._fields_purchase_book_line(move, dict(self.sample_taxes))

    def test_fields_sale_book_line_regular_invoice(self):
        self.wizard.write({"report": "sale"})
        move = self._fake_move(
            move_type="out_invoice",
            vat=False,
            correlative=False,
        )

        line = self.wizard._fields_sale_book_line(move, dict(self.sample_taxes))

        self.assertEqual(line["_id"], move.id)
        self.assertEqual(line["document_date"], "10/01/2023")
        self.assertEqual(line["accounting_date"], "10/01/2023")
        self.assertEqual(line["vat"], "--")
        self.assertEqual(line["partner_name"], "Partner Demo")
        self.assertEqual(line["document_number"], "MOVE/2023/0001")
        self.assertEqual(line["move_type"], "FAC")
        self.assertEqual(line["transaction_type"], "01-REG")
        self.assertEqual(line["number_invoice_affected"], "--")
        self.assertEqual(line["correlative"], "--")
        self.assertEqual(line["total_sales"], 150.0)
        self.assertEqual(line["total_sales_iva"], 100.0)
        self.assertEqual(line["total_sales_not_iva"], 50.0)

    def test_fields_sale_book_line_refund_applies_negative_multiplier(self):
        self.wizard.write({"report": "sale"})
        move = self._fake_move(
            move_type="out_refund",
            reversed_entry_id=SimpleNamespace(name="INV/2023/0001"),
            correlative="CTRL-SALE-REF",
        )

        line = self.wizard._fields_sale_book_line(move, dict(self.sample_taxes))

        self.assertEqual(line["move_type"], "NC")
        self.assertEqual(line["transaction_type"], "03-REG")
        self.assertEqual(line["number_invoice_affected"], "INV/2023/0001")
        self.assertEqual(line["correlative"], "CTRL-SALE-REF")
        self.assertEqual(line["total_sales"], 150.0)
        self.assertEqual(line["total_sales_iva"], 200.0)
        self.assertEqual(line["total_sales_not_iva"], -50.0)
        self.assertEqual(line["amount_reduced_aliquot"], -8.0)
        self.assertEqual(line["amount_general_aliquot"], -16.0)
        self.assertEqual(line["amount_extend_aliquot"], -31.0)

    def test_fields_sale_book_line_raises_if_posted_without_invoice_date(self):
        self.wizard.write({"report": "sale"})
        move = self._fake_move(move_type="out_invoice", invoice_date=False)

        with self.assertRaisesRegex(UserError, "invoice date"):
            self.wizard._fields_sale_book_line(move, dict(self.sample_taxes))

    def test_parse_sale_book_data_calls_full_flow(self):
        move_1 = self._fake_move(id=1, name="A")
        move_2 = self._fake_move(id=2, name="B")

        with patch.object(type(self.wizard), "search_moves", return_value=[move_1, move_2]), patch.object(
            type(self.wizard),
            "_determinate_amount_taxeds",
            side_effect=[{"amount_taxed": 10}, {"amount_taxed": 20}],
        ), patch.object(
            type(self.wizard),
            "_fields_sale_book_line",
            side_effect=[{"document_number": "A"}, {"document_number": "B"}],
        ):
            result = self.wizard.parse_sale_book_data()

        self.assertEqual(result, [{"document_number": "A"}, {"document_number": "B"}])

    def test_parse_purchase_book_data_skips_false_lines(self):
        move_1 = self._fake_move(id=1, name="A")
        move_2 = self._fake_move(id=2, name="B")

        with patch.object(type(self.wizard), "search_moves", return_value=[move_1, move_2]), patch.object(
            type(self.wizard),
            "_determinate_amount_taxeds",
            side_effect=[{"amount_taxed": 10}, {"amount_taxed": 20}],
        ), patch.object(
            type(self.wizard),
            "_fields_purchase_book_line",
            side_effect=[{"document_number": "A"}, False],
        ):
            result = self.wizard.parse_purchase_book_data()

        self.assertEqual(result, [{"document_number": "A"}])

    def test_determinate_resume_books_for_all_tax_types(self):
        move_regular = self._create_move(
            name="BILL/2023/0100",
            move_type="in_invoice",
            accounting_date=date(2023, 1, 10),
        )
        move_refund = self._create_move(
            name="REF/2023/0100",
            move_type="in_refund",
            accounting_date=date(2023, 1, 11),
        )
        move_outside = self._create_move(
            name="BILL/2023/OUTSIDE",
            move_type="in_invoice",
            accounting_date=date(2023, 2, 1),
        )
        moves = move_regular | move_refund | move_outside

        values_by_move = {
            move_regular.id: {
                "tax_base_exempt_aliquot": 10.0,
                "amount_exempt_aliquot": 0.0,
                "tax_base_general_aliquot": 100.0,
                "amount_general_aliquot": 16.0,
                "tax_base_reduced_aliquot": 50.0,
                "amount_reduced_aliquot": 4.0,
                "tax_base_extend_aliquot": 70.0,
                "amount_extend_aliquot": 21.7,
                "tax_base_general_aliquot_international": 80.0,
                "amount_general_aliquot_international": 12.8,
                "tax_base_extend_aliquot_international": 90.0,
                "amount_extend_aliquot_international": 27.9,
            },
            move_refund.id: {
                "tax_base_exempt_aliquot": 3.0,
                "amount_exempt_aliquot": 0.0,
                "tax_base_general_aliquot": 20.0,
                "amount_general_aliquot": 3.2,
                "tax_base_reduced_aliquot": 10.0,
                "amount_reduced_aliquot": 0.8,
                "tax_base_extend_aliquot": 15.0,
                "amount_extend_aliquot": 4.65,
                "tax_base_general_aliquot_international": 12.0,
                "amount_general_aliquot_international": 1.92,
                "tax_base_extend_aliquot_international": 14.0,
                "amount_extend_aliquot_international": 4.34,
            },
            move_outside.id: {
                "tax_base_exempt_aliquot": 999.0,
                "amount_exempt_aliquot": 999.0,
                "tax_base_general_aliquot": 999.0,
                "amount_general_aliquot": 999.0,
                "tax_base_reduced_aliquot": 999.0,
                "amount_reduced_aliquot": 999.0,
                "tax_base_extend_aliquot": 999.0,
                "amount_extend_aliquot": 999.0,
                "tax_base_general_aliquot_international": 999.0,
                "amount_general_aliquot_international": 999.0,
                "tax_base_extend_aliquot_international": 999.0,
                "amount_extend_aliquot_international": 999.0,
            },
        }

        def amount_side_effect(_wizard, move):
            return values_by_move[move.id]

        expectations = {
            "exempt_aliquot": [10.0, 0.0, -3.0, 0.0],
            "general_aliquot": [100.0, 16.0, -20.0, -3.2],
            "reduced_aliquot": [50.0, 4.0, -10.0, -0.8],
            "extend_aliquot": [70.0, 21.7, -15.0, -4.65],
            "general_aliquot_international": [80.0, 12.8, -12.0, -1.92],
            "extend_aliquot_international": [90.0, 27.9, -14.0, -4.34],
        }

        with patch.object(type(self.wizard), "_determinate_amount_taxeds", autospec=True, side_effect=amount_side_effect):
            for tax_type, expected in expectations.items():
                with self.subTest(tax_type=tax_type):
                    result = self.wizard._determinate_resume_books(moves, tax_type)
                    self.assertEqual(len(result), len(expected))
                    for index, expected_value in enumerate(expected):
                        self.assertAlmostEqual(result[index], expected_value, places=2)

            self.assertEqual(self.wizard._determinate_resume_books(moves), [0.0, 0.0, 0.0, 0.0])

    def test_sale_book_fields_flattens_groups(self):
        groups = [
            {"header": "A", "fields": [{"field": "one"}, {"field": "two"}]},
            {"header": "B", "fields": [{"field": "three"}]},
        ]
        with patch.object(type(self.wizard), "_get_sale_book_field_groups", return_value=groups):
            fields = self.wizard.sale_book_fields()
        self.assertEqual([field["field"] for field in fields], ["one", "two", "three"])

    def test_purchase_book_fields_flattens_groups(self):
        groups = [
            {"header": "A", "fields": [{"field": "one"}, {"field": "two"}]},
            {"header": "B", "fields": [{"field": "three"}]},
        ]
        with patch.object(type(self.wizard), "_get_purchase_book_field_groups", return_value=groups):
            fields = self.wizard.purchase_book_fields()
        self.assertEqual([field["field"] for field in fields], ["one", "two", "three"])

    def test_resume_book_headers_for_purchase_and_sale(self):
        self.wizard.write({"report": "purchase"})
        purchase_headers = self.wizard.resume_book_headers()
        self.assertIn("Créditos Fiscales", purchase_headers[0]["headers"][1])

        self.wizard.write({"report": "sale"})
        sale_headers = self.wizard.resume_book_headers()
        self.assertIn("Débitos Fiscales", sale_headers[0]["headers"][1])

    def test_get_domain_purchase_adds_international_filter_when_hidden(self):
        self.wizard.write({"report": "purchase"})
        self._write_company_flags(
            not_show_general_aliquot_purchase_international=True,
            not_show_reduced_aliquot_purchase_international=True,
            not_show_extend_aliquot_purchase_international=True,
            not_show_total_purchases_with_international_iva=True,
            not_show_exempt_total_purchases=True,
            not_show_total_purchases_international=True,
        )

        domain = self.wizard._get_domain()

        self.assertIn(("company_id", "=", self.company.id), domain)
        self.assertIn(("journal_id.is_purchase_international", "=", False), domain)
        self.assertIn(("state", "in", ["posted"]), domain)
        self.assertIn(("move_type", "in", ["in_invoice", "in_refund", "in_debit"]), domain)

    def test_get_domain_sale_uses_sale_states(self):
        self.wizard.write({"report": "sale"})
        domain = self.wizard._get_domain()

        self.assertIn(("company_id", "=", self.company.id), domain)
        self.assertIn(("state", "in", ["posted", "cancel"]), domain)
        self.assertIn(("move_type", "in", ["out_invoice", "out_refund"]), domain)
        self.assertIn(("correlative", "not in", ["/", False]), domain)

    def test_generate_report_dispatches_by_report_type(self):
        self.wizard.write({"report": "sale"})
        with patch.object(type(self.wizard), "download_sales_book", return_value={"url": "sale"}) as sale_mock:
            self.assertEqual(self.wizard.generate_report(), {"url": "sale"})
            sale_mock.assert_called_once()

        self.wizard.write({"report": "purchase"})
        with patch.object(type(self.wizard), "download_purchases_book", return_value={"url": "purchase"}) as purchase_mock:
            self.assertEqual(self.wizard.generate_report(), {"url": "purchase"})
            purchase_mock.assert_called_once()

    def test_download_actions(self):
        sale_wizard = self.wizard_model.create(
            {
                "report": "sale",
                "date_from": "2023-01-01",
                "date_to": "2023-01-31",
                "company_id": self.company.id,
            }
        )
        purchase_action = self.wizard.download_purchases_book()
        sale_action = sale_wizard.download_sales_book()

        self.assertEqual(purchase_action["type"], "ir.actions.act_url")
        self.assertIn("/web/download_purchase_book", purchase_action["url"])
        self.assertEqual(sale_action["type"], "ir.actions.act_url")
        self.assertIn("/web/download_sales_book", sale_action["url"])

    def test_determinate_type_mapping_and_cancel_transaction(self):
        self.assertEqual(self.wizard._determinate_type("out_debit"), "ND")
        self.assertEqual(self.wizard._determinate_type("out_invoice"), "FAC")
        self.assertEqual(self.wizard._determinate_type("out_refund"), "NC")

        move = self._fake_move(
            move_type="out_invoice",
            state="cancel",
            journal_id=self._fake_journal(),
        )
        self.assertEqual(self.wizard._determinate_transaction_type(move), "03-ANU")

    def test_search_moves_order_purchase(self):
        move_2 = self._create_move(
            name="BILL/2023/0008",
            move_type="in_invoice",
            invoice_date=date(2023, 1, 5),
            correlative="CTRL-B",
        )
        move_1 = self._create_move(
            name="BILL/2023/0007",
            move_type="in_invoice",
            invoice_date=date(2023, 1, 20),
            correlative="CTRL-A",
        )
        move_cancel = self._create_move(
            name="BILL/2023/CANCEL",
            move_type="in_invoice",
            invoice_date=date(2023, 1, 3),
            state="cancel",
            correlative="CTRL-C",
        )

        self.wizard.write({"report": "purchase"})
        moves = self.wizard.search_moves()

        self.assertEqual(moves[:2].ids, (move_2 | move_1).ids)
        self.assertNotIn(move_cancel.id, moves.ids)

    def test_search_moves_order_sale(self):
        move_b = self._create_move(
            name="OUT/2023/0002",
            move_type="out_invoice",
            journal=self.sale_journal,
            invoice_date=date(2023, 1, 10),
            correlative="B-002",
        )
        move_a = self._create_move(
            name="OUT/2023/0001",
            move_type="out_invoice",
            journal=self.sale_journal,
            invoice_date=date(2023, 1, 20),
            correlative="A-001",
        )
        move_c_cancel = self._create_move(
            name="OUT/2023/0003",
            move_type="out_refund",
            journal=self.sale_journal,
            invoice_date=date(2023, 1, 15),
            state="cancel",
            correlative="C-003",
        )

        self.wizard.write({"report": "sale"})
        moves = self.wizard.search_moves()

        self.assertEqual(moves[:3].ids, [move_a.id, move_b.id, move_c_cancel.id])
        self.assertIn(move_c_cancel.id, moves.ids)

    def test_resume_sale_and_purchase_book_fields(self):
        moves = self.env["account.move"]

        def resume_side_effect(_wizard, _moves, tax_type=None):
            return [tax_type or "default", 1, 2, 3]

        with patch.object(type(self.wizard), "_determinate_resume_books", autospec=True, side_effect=resume_side_effect):
            sale_resume = self.wizard._resume_sale_book_fields(moves)
            purchase_resume = self.wizard._resume_purchase_book_fields(moves)

        self.assertEqual(len(sale_resume), 6)
        self.assertTrue(sale_resume[-1]["total"])
        self.assertEqual(len(purchase_resume), 8)
        self.assertTrue(purchase_resume[-1]["total"])

    def test_determinate_amount_taxeds_not_posted_returns_zeroes(self):
        self._setup_company_tax_configuration()
        self.wizard.write({"report": "purchase"})
        move = self._fake_move(
            state="cancel",
            move_type="in_invoice",
            tax_totals={},
        )

        result = self.wizard._determinate_amount_taxeds(move)

        self.assertEqual(result["amount_untaxed"], 0.0)
        self.assertEqual(result["amount_taxed"], 0.0)
        self.assertEqual(result["tax_base_general_aliquot"], 0.0)
        self.assertEqual(result["amount_general_aliquot"], 0.0)
        self.assertIn("tax_base_general_aliquot_no_deductible", result)

    def test_determinate_amount_taxeds_without_tax_totals_returns_defaults(self):
        self._setup_company_tax_configuration()
        self.wizard.write({"report": "purchase"})
        move = self._fake_move(
            state="posted",
            move_type="in_invoice",
            tax_totals=False,
        )

        result = self.wizard._determinate_amount_taxeds(move)

        self.assertEqual(result["amount_untaxed"], 0)
        self.assertEqual(result["amount_taxed"], 0)
        self.assertEqual(result["amount_import_international"], 0)

    def test_determinate_amount_taxeds_sale_with_tax_groups(self):
        self._setup_company_tax_configuration()
        self.wizard.write({"report": "sale", "currency_system": True})

        move = self._fake_move(
            move_type="out_invoice",
            journal_id=self._fake_journal(),
            tax_totals={
                "amount_untaxed": 100.0,
                "amount_total": 128.0,
                "groups_by_subtotal": {
                    "Untaxed Amount": [
                        {
                            "tax_group_id": self.company.exent_aliquot_sale.tax_group_id.id,
                            "tax_group_base_amount": 10.0,
                            "tax_group_amount": 0.0,
                        },
                        {
                            "tax_group_id": self.company.general_aliquot_sale.tax_group_id.id,
                            "tax_group_base_amount": 50.0,
                            "tax_group_amount": 8.0,
                        },
                        {
                            "tax_group_id": self.company.reduced_aliquot_sale.tax_group_id.id,
                            "tax_group_base_amount": 20.0,
                            "tax_group_amount": 1.6,
                        },
                        {
                            "tax_group_id": self.company.extend_aliquot_sale.tax_group_id.id,
                            "tax_group_base_amount": 20.0,
                            "tax_group_amount": 6.2,
                        },
                    ]
                },
            },
        )

        result = self.wizard._determinate_amount_taxeds(move)

        self.assertAlmostEqual(result["amount_untaxed"], 100.0, places=2)
        self.assertAlmostEqual(result["amount_taxed"], 128.0, places=2)
        self.assertAlmostEqual(result["tax_base_exempt_aliquot"], 10.0, places=2)
        self.assertAlmostEqual(result["tax_base_general_aliquot"], 50.0, places=2)
        self.assertAlmostEqual(result["amount_general_aliquot"], 8.0, places=2)
        self.assertAlmostEqual(result["tax_base_reduced_aliquot"], 20.0, places=2)
        self.assertAlmostEqual(result["amount_reduced_aliquot"], 1.6, places=2)
        self.assertAlmostEqual(result["tax_base_extend_aliquot"], 20.0, places=2)
        self.assertAlmostEqual(result["amount_extend_aliquot"], 6.2, places=2)

    def test_determinate_amount_taxeds_purchase_international_and_foreign_currency(self):
        self._setup_company_tax_configuration()
        self.wizard.write({"report": "purchase", "currency_system": False})

        move = self._fake_move(
            move_type="in_invoice",
            journal_id=self._fake_journal(is_purchase_international=True),
            tax_totals={
                "foreign_amount_untaxed": 100.0,
                "foreign_amount_total": 136.8,
                "groups_by_foreign_subtotal": {
                    "Untaxed Amount": [
                        {
                            "tax_group_id": self.company.exent_aliquot_purchase_international.tax_group_id.id,
                            "tax_group_base_amount": 10.0,
                            "tax_group_amount": 0.0,
                        },
                        {
                            "tax_group_id": self.company.general_aliquot_purchase_international.tax_group_id.id,
                            "tax_group_base_amount": 50.0,
                            "tax_group_amount": 8.0,
                        },
                        {
                            "tax_group_id": self.company.reduced_aliquot_purchase_international.tax_group_id.id,
                            "tax_group_base_amount": 20.0,
                            "tax_group_amount": 1.6,
                        },
                        {
                            "tax_group_id": self.company.extend_aliquot_purchase_international.tax_group_id.id,
                            "tax_group_base_amount": 30.0,
                            "tax_group_amount": 9.2,
                        },
                    ]
                },
            },
        )

        result = self.wizard._determinate_amount_taxeds(move)

        self.assertAlmostEqual(result["amount_untaxed"], 100.0, places=2)
        self.assertAlmostEqual(result["amount_taxed"], 136.8, places=2)
        self.assertAlmostEqual(result["international_amount_taxed"], 136.8, places=2)
        self.assertAlmostEqual(result["international_tax_base_exempt_aliquot"], 10.0, places=2)
        self.assertAlmostEqual(result["tax_base_general_aliquot_international"], 50.0, places=2)
        self.assertAlmostEqual(result["amount_general_aliquot_international"], 8.0, places=2)
        self.assertAlmostEqual(result["tax_base_reduced_aliquot_international"], 20.0, places=2)
        self.assertAlmostEqual(result["amount_reduced_aliquot_international"], 1.6, places=2)
        self.assertAlmostEqual(result["tax_base_extend_aliquot_international"], 30.0, places=2)
        self.assertAlmostEqual(result["amount_extend_aliquot_international"], 9.2, places=2)
        self.assertAlmostEqual(result["amount_import_international"], 128.8, places=2)

    def test_determinate_amount_taxeds_purchase_no_deductible(self):
        self._setup_company_tax_configuration()
        self.wizard.write({"report": "purchase", "currency_system": True})

        move = self._fake_move(
            move_type="in_invoice",
            journal_id=self._fake_journal(),
            tax_totals={
                "amount_untaxed": 100.0,
                "amount_total": 132.8,
                "groups_by_subtotal": {
                    "Untaxed Amount": [
                        {
                            "tax_group_id": self.company.general_aliquot_purchase.tax_group_id.id,
                            "tax_group_base_amount": 50.0,
                            "tax_group_amount": 8.0,
                        },
                        {
                            "tax_group_id": self.company.reduced_aliquot_purchase.tax_group_id.id,
                            "tax_group_base_amount": 10.0,
                            "tax_group_amount": 0.8,
                        },
                        {
                            "tax_group_id": self.company.extend_aliquot_purchase.tax_group_id.id,
                            "tax_group_base_amount": 10.0,
                            "tax_group_amount": 3.1,
                        },
                        {
                            "tax_group_id": self.company.no_deductible_general_aliquot_purchase.tax_group_id.id,
                            "tax_group_base_amount": 20.0,
                            "tax_group_amount": 3.2,
                        },
                        {
                            "tax_group_id": self.company.no_deductible_reduced_aliquot_purchase.tax_group_id.id,
                            "tax_group_base_amount": 5.0,
                            "tax_group_amount": 0.4,
                        },
                        {
                            "tax_group_id": self.company.no_deductible_extend_aliquot_purchase.tax_group_id.id,
                            "tax_group_base_amount": 5.0,
                            "tax_group_amount": 1.55,
                        },
                    ]
                },
            },
        )

        result = self.wizard._determinate_amount_taxeds(move)

        self.assertAlmostEqual(result["national_amount_taxed"], 132.8, places=2)
        self.assertAlmostEqual(result["tax_base_general_aliquot"], 50.0, places=2)
        self.assertAlmostEqual(result["amount_general_aliquot"], 8.0, places=2)
        self.assertAlmostEqual(result["tax_base_reduced_aliquot_no_deductible"], 5.0, places=2)
        self.assertAlmostEqual(result["amount_reduced_aliquot_no_deductible"], 0.4, places=2)
        self.assertAlmostEqual(result["tax_base_general_aliquot_no_deductible"], 20.0, places=2)
        self.assertAlmostEqual(result["amount_general_aliquot_no_deductible"], 3.2, places=2)
        self.assertAlmostEqual(result["tax_base_extend_aliquot_no_deductible"], 5.0, places=2)
        self.assertAlmostEqual(result["amount_extend_aliquot_no_deductible"], 1.55, places=2)

    def test_generate_book_resume_raises_when_no_moves(self):
        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
        worksheet = workbook.add_worksheet()
        merge_format = workbook.add_format()
        cell_formats = {"number": workbook.add_format({"num_format": "#,##0.00"})}

        with patch.object(type(self.wizard), "search_moves", return_value=self.env["account.move"]):
            with self.assertRaisesRegex(UserError, "There are no moves to show"):
                self.wizard.generate_book_resume(worksheet, 10, merge_format, cell_formats)

        workbook.close()

    def test_generate_book_resume_for_sale_and_purchase(self):
        move = self._create_move(
            name="BILL/2023/RESUME",
            move_type="in_invoice",
            accounting_date=date(2023, 1, 10),
        )
        moves = self.env["account.move"].browse(move.id)

        for report_type, method_name in [("purchase", "_resume_purchase_book_fields"), ("sale", "_resume_sale_book_fields")]:
            with self.subTest(report_type=report_type):
                self.wizard.write({"report": report_type})
                buffer = BytesIO()
                workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
                worksheet = workbook.add_worksheet()
                merge_format = workbook.add_format()
                cell_formats = {"number": workbook.add_format({"num_format": "#,##0.00"})}

                resume_lines = [
                    {"name": "L1", "values": [1.0, 2.0, 3.0, 4.0]},
                    {"name": "TOTAL", "values": [0.0, 0.0, 0.0, 0.0], "total": True},
                ]

                with patch.object(type(self.wizard), "search_moves", return_value=moves), patch.object(
                    type(self.wizard), method_name, return_value=resume_lines
                ):
                    self.wizard.generate_book_resume(worksheet, 10, merge_format, cell_formats)

                workbook.close()

    def test_generate_sales_book_returns_xlsx(self):
        self.wizard.write({"report": "sale"})
        sale_lines = [
            {
                "document_number": "INV-1",
                "partner_name": "Cliente 1",
                "total_sales": 100.0,
                "tax_base_extend_aliquot": 100.0,
                "amount_extend_aliquot": 31.0,
            }
        ]
        sale_groups = [
            {
                "header": "DETALLE DEL DOCUMENTO",
                "fields": [
                    {"name": "N° operacion", "field": "index"},
                    {"name": "N° de documento", "field": "document_number"},
                ],
            },
            {
                "header": "TOTALES",
                "fields": [
                    {"name": "Cliente", "field": "partner_name"},
                    {"name": "Total ventas", "field": "total_sales", "format": "number"},
                ],
            },
            {
                "header": "ALÍCUOTA ADICIONAL (31%)",
                "fields": [
                    {"name": "Base 31%", "field": "tax_base_extend_aliquot", "format": "number"},
                    {"name": "IVA 31%", "field": "amount_extend_aliquot", "format": "number"},
                ],
            },
        ]

        with patch.object(type(self.wizard), "parse_sale_book_data", return_value=sale_lines), patch.object(
            type(self.wizard), "_get_sale_book_field_groups", return_value=sale_groups
        ), patch.object(type(self.wizard), "generate_book_resume", return_value=None):
            content = self.wizard.generate_sales_book(self.company.id)

        self.assertTrue(content.startswith(b"PK"))

    def test_generate_sales_book_returns_xlsx_without_additional_group(self):
        self.wizard.write({"report": "sale"})
        sale_lines = [
            {
                "document_number": "INV-1",
                "partner_name": "Cliente 1",
                "total_sales": 100.0,
            }
        ]
        sale_groups = [
            {
                "header": "DETALLE DEL DOCUMENTO",
                "fields": [
                    {"name": "N° operacion", "field": "index"},
                    {"name": "N° de documento", "field": "document_number"},
                ],
            },
            {
                "header": "TOTALES",
                "fields": [
                    {"name": "Cliente", "field": "partner_name"},
                    {"name": "Total ventas", "field": "total_sales", "format": "number"},
                ],
            },
        ]

        with patch.object(type(self.wizard), "parse_sale_book_data", return_value=sale_lines), patch.object(
            type(self.wizard), "_get_sale_book_field_groups", return_value=sale_groups
        ), patch.object(type(self.wizard), "generate_book_resume", return_value=None):
            content = self.wizard.generate_sales_book(self.company.id)

        self.assertTrue(content.startswith(b"PK"))

    def test_generate_purchases_book_returns_xlsx(self):
        self.wizard.write({"report": "purchase"})
        purchase_lines = [
            {
                "document_number": "BILL-1",
                "partner_name": "Proveedor 1",
                "total_purchases": 100.0,
            }
        ]
        purchase_groups = [
            {
                "header": "DETALLE DEL DOCUMENTO",
                "fields": [
                    {"name": "N° operacion", "field": "index"},
                    {"name": "N° de documento", "field": "document_number"},
                ],
            },
            {
                "header": "TOTALES",
                "fields": [
                    {"name": "Proveedor", "field": "partner_name"},
                    {"name": "Total compras", "field": "total_purchases", "format": "number"},
                ],
            },
        ]

        with patch.object(type(self.wizard), "parse_purchase_book_data", return_value=purchase_lines), patch.object(
            type(self.wizard), "_get_purchase_book_field_groups", return_value=purchase_groups
        ), patch.object(type(self.wizard), "generate_book_resume", return_value=None):
            content = self.wizard.generate_purchases_book(self.company.id)

        self.assertTrue(content.startswith(b"PK"))

    def test_get_sale_book_field_groups_respects_company_flags(self):
        self._setup_company_tax_configuration()
        self.wizard.write({"report": "sale"})

        self._write_company_flags(
            not_show_reduced_aliquot_sale=False,
            not_show_extend_aliquot_sale=False,
        )
        groups = self.wizard._get_sale_book_field_groups()
        fields_list = [field["field"] for group in groups for field in group["fields"]]

        self.assertIn("tax_base_reduced_aliquot", fields_list)
        self.assertIn("amount_reduced_aliquot", fields_list)
        self.assertIn("tax_base_extend_aliquot", fields_list)
        self.assertIn("amount_extend_aliquot", fields_list)

        self._write_company_flags(
            not_show_reduced_aliquot_sale=True,
            not_show_extend_aliquot_sale=True,
        )
        groups = self.wizard._get_sale_book_field_groups()
        fields_list = [field["field"] for group in groups for field in group["fields"]]

        self.assertNotIn("tax_base_reduced_aliquot", fields_list)
        self.assertNotIn("amount_reduced_aliquot", fields_list)
        self.assertNotIn("tax_base_extend_aliquot", fields_list)
        self.assertNotIn("amount_extend_aliquot", fields_list)

    def test_get_purchase_book_field_groups_respects_company_flags(self):
        self._setup_company_tax_configuration()
        self.wizard.write({"report": "purchase"})

        self._write_company_flags(
            config_deductible_tax=True,
            not_show_total_purchases_national=False,
            not_show_total_purchases_with_iva=False,
            not_show_national_exempt_total_purchases=False,
            not_show_total_purchases_international=False,
            not_show_total_purchases_with_international_iva=False,
            not_show_exempt_total_purchases=False,
            not_show_reduced_aliquot_purchase=False,
            not_show_extend_aliquot_purchase=False,
            not_show_general_aliquot_purchase_international=False,
            not_show_reduced_aliquot_purchase_international=False,
            not_show_extend_aliquot_purchase_international=False,
        )
        groups = self.wizard._get_purchase_book_field_groups()
        headers = [group["header"] for group in groups]
        self.assertIn("TOTALES NACIONALES", headers)
        self.assertIn("COMPRAS INTERNACIONALES", headers)
        self.assertIn("IMPUESTOS NO DEDUCIBLES", headers)

        self._write_company_flags(
            config_deductible_tax=False,
            not_show_total_purchases_national=True,
            not_show_total_purchases_with_iva=True,
            not_show_national_exempt_total_purchases=True,
            not_show_total_purchases_international=True,
            not_show_total_purchases_with_international_iva=True,
            not_show_exempt_total_purchases=True,
            not_show_reduced_aliquot_purchase=True,
            not_show_extend_aliquot_purchase=True,
            not_show_general_aliquot_purchase_international=True,
            not_show_reduced_aliquot_purchase_international=True,
            not_show_extend_aliquot_purchase_international=True,
        )
        groups = self.wizard._get_purchase_book_field_groups()
        headers = [group["header"] for group in groups]
        self.assertNotIn("TOTALES NACIONALES", headers)
        self.assertNotIn("COMPRAS INTERNACIONALES", headers)
        self.assertNotIn("IMPUESTOS NO DEDUCIBLES", headers)

    def test_default_date_to_returns_today(self):
        wizard = self.wizard_model.create({"report": "sale"})

        self.assertEqual(wizard._default_date_to(), fields.Date.today())

    def test_default_date_from_returns_previous_month(self):
        wizard = self.wizard_model.create({"report": "sale"})

        self.assertEqual(
            wizard._default_date_from(),
            fields.Date.today() + relativedelta(months=-1),
        )

    def test_default_company_id_returns_current_company(self):
        wizard = self.wizard_model.create({"report": "sale"})

        self.assertEqual(
            self.env["res.company"].browse(wizard._default_company_id()),
            self.env.company,
        )

    def test_default_check_currency_system_returns_false_for_non_vef(self):
        wizard = self.wizard_model.create({"report": "sale"})

        self.assertFalse(wizard._default_check_currency_system())

    def test_default_currency_system_returns_false_for_non_vef(self):
        wizard = self.wizard_model.create({"report": "sale"})

        self.assertFalse(wizard._default_currency_system())

    def test_default_check_currency_system_returns_true_for_vef(self):
        self.company.write(
            {
                "currency_id": self.env.ref("base.VEF").id,
                "currency_foreign_id": self.env.ref("base.USD").id,
            }
        )
        wizard = self.wizard_model.create({"report": "sale"})

        self.assertTrue(wizard._default_check_currency_system())

    def test_default_currency_system_returns_true_for_vef(self):
        self.company.write(
            {
                "currency_id": self.env.ref("base.VEF").id,
                "currency_foreign_id": self.env.ref("base.USD").id,
            }
        )
        wizard = self.wizard_model.create({"report": "sale"})

        self.assertTrue(wizard._default_currency_system())
