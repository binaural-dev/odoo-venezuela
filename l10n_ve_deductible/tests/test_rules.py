from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools import file_open
from odoo.tools.translate import PoFileReader

from .common import DeductibleCase


class TestDeductibleRules(DeductibleCase):
    """Validations of the deductible: limits, exempt taxes, previous discounts,
    document types, draft-only edition and what duplicates and extra lines do."""

    def test_percent_and_reference_amount(self):
        doc = self._doc([(100.0, 1), (300.0, 1)], **self.PERCENT | {"global_deductible_percent": 10.0})
        self.assertEqual(doc.amount_total, 360.0)
        self.assertEqual(doc.global_deductible_reference_amount, 40.0)

    def test_fixed_amount_is_shared_among_the_lines(self):
        doc = self._doc([(100.0, 1), (200.0, 1), (300.0, 1)], **self.AMOUNT | {"global_deductible_amount": 100.0})
        self.assertEqual(doc.amount_total, 500.0)
        self.assertEqual(round(sum(doc.invoice_line_ids.mapped("global_deductible_line_amount")), 2), 100.0)

    def test_amount_limits(self):
        for amount in (0.0, 400.0, 500.0):
            with self.assertRaisesMsg(ValidationError, "less than the original document total"):
                self._doc([(100.0, 1), (300.0, 1)], **self.AMOUNT | {"global_deductible_amount": amount})

    def test_percent_limits(self):
        for percent in (0.0, 100.0):
            with self.assertRaisesMsg(ValidationError, "greater than 0 and less than 100"):
                self._doc(**self.PERCENT | {"global_deductible_percent": percent})

    def test_taxed_lines_are_allowed(self):
        """The deductible is not limited to exempt taxes: general, fixed and
        mixed-tax documents accept it and the tax is computed on the base
        left after the deductible."""
        for kind in ("general", "fixed"):
            with self.subTest(kind=kind):
                doc = self._doc(tax=self.tax(kind), **self.PERCENT)
                self.assertTrue(doc.is_deductible)
        general = self._doc([(100.0, 1), (300.0, 1)], tax=self.tax("general"), **self.PERCENT | {"global_deductible_percent": 10.0})
        self.assertEqual(general.amount_untaxed, 360.0)
        self.assertEqual(general.amount_tax, 57.6)
        self.assertEqual(general.amount_total, 417.6)
        self.assertEqual(general.global_deductible_reference_amount, 40.0)

    def test_taxed_and_exempt_lines_mixed(self):
        taxes = (self.tax("general"), self.tax("exempt"))
        lines = [
            Command.create(
                {"product_id": self.product.id, "name": f"L{i}", "quantity": 1, "price_unit": 100.0,
                 "tax_ids": [Command.set(tax.ids)]}
            )
            for i, tax in enumerate(taxes)
        ]
        doc = self._doc(invoice_line_ids=lines, **self.PERCENT | {"global_deductible_percent": 50.0})
        self.assertEqual(doc.amount_untaxed, 100.0)
        self.assertEqual(doc.amount_tax, 8.0)

    def test_taxed_line_can_be_added_and_activation_has_no_warning(self):
        plain = self._doc(tax=self.tax("general"))
        result = plain.onchange({"is_deductible": True}, ["is_deductible"], {"is_deductible": {}})
        self.assertNotIn("warning", result)
        doc = self._doc(**self.PERCENT)
        new_line = Command.create(
            {"product_id": self.product.id, "name": "IVA", "price_unit": 5.0, "tax_ids": [Command.set(self.tax("general").ids)]}
        )
        doc.write({"invoice_line_ids": [new_line]})
        doc.invoice_line_ids[0].tax_ids = self.tax("general")
        self.assertTrue(doc.is_deductible)

    def test_fixed_amount_with_taxed_lines(self):
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                doc = self._doc(tax=self.tax("general"), currency=currency, **self.AMOUNT)
                self.assertEqual(round(sum(doc.invoice_line_ids.mapped("global_deductible_line_amount")), 2), 77.77)

    def test_price_included_exempt_tax_matches_native_discount(self):
        lines = [(100.0, 2), (33.3333, 3)]
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                mine = self._doc(lines, currency, tax=self.tax("included"), **self.PERCENT)
                native = self._doc(lines, currency, tax=self.tax("included"), line_extra={"discount": 12.5})
                self._assert_same(mine, native)

    def test_previous_discount_is_rejected(self):
        doc = self._doc(**self.PERCENT)
        with self.assertRaisesMsg(ValidationError, "cannot have lines with a discount"):
            doc.invoice_line_ids[0].discount = 5.0

    def test_unsupported_documents(self):
        for move_type in ("in_receipt", "out_receipt", "in_refund", "out_refund"):
            with self.subTest(move_type=move_type), self.assertRaisesMsg(ValidationError, "only be used on"):
                self._doc(move_type=move_type, **self.PERCENT)

    def test_deactivation_reverts_everything(self):
        doc = self._doc(**self.AMOUNT)
        doc.is_deductible = False
        self.assertEqual((doc.global_deductible_percent, doc.global_deductible_amount), (0.0, 0.0))
        self.assertFalse(any(doc.invoice_line_ids.mapped("global_deductible_discount_percent")))
        self.assertFalse(any(doc.invoice_line_ids.mapped("global_deductible_line_amount")))
        self.assertFalse(doc.tax_totals.get("is_deductible"))
        self._assert_same(doc, self._doc())

    def test_edition_only_in_draft(self):
        doc = self._post(self._doc(**self.AMOUNT))
        for vals in ({"global_deductible_percent": 5.0}, {"is_deductible": False}):
            with self.assertRaisesMsg(UserError, "draft documents"):
                doc.write(vals)
        doc.button_draft()
        doc.is_deductible = False
        self.assertEqual((doc.global_deductible_percent, doc.global_deductible_amount), (0.0, 0.0))
        self.assertFalse(any(doc.invoice_line_ids.mapped("global_deductible_line_amount")))
        self.assertEqual(doc.amount_untaxed, self._doc().amount_untaxed)

    def test_changing_the_scope_does_not_lock_existing_documents(self):
        draft = self._doc(**self.AMOUNT)
        posted = self._post(self._doc(**self.AMOUNT))
        self.company.deductible_scope = "customer" if self.MOVE_TYPE == "in_invoice" else "vendor"
        self.assertFalse(draft.deductible_allowed)
        before = draft.amount_total
        draft.invoice_line_ids[0].price_unit = 55.5
        self.assertNotEqual(draft.amount_total, before)
        credit, replacement = self._reverse(posted)
        self.assertTrue(credit.is_deductible and replacement.is_deductible)
        self.assertTrue(self._debit(posted, copy_lines=True).is_deductible)
        with self.assertRaisesMsg(ValidationError, "not enabled for this company"):
            self._doc().write(self.PERCENT)

    def test_duplicate_does_not_carry_the_deductible(self):
        copy = self._doc(**self.AMOUNT).copy()
        self.assertFalse(copy.is_deductible)
        self.assertFalse(any(copy.invoice_line_ids.mapped("global_deductible_line_amount")))
        self.assertEqual(copy.amount_untaxed, self._doc().amount_untaxed)

    def test_sections_and_notes_are_ignored(self):
        for method, currency in self._combos():
            with self.subTest(method=method, currency=currency.name):
                lines = [Command.create({"display_type": "line_section", "name": "Sección"})]
                lines += [
                    Command.create(
                        {"product_id": self.product.id, "name": "L", "quantity": qty, "price_unit": price,
                         "tax_ids": [Command.set(self.tax().ids)]}
                    )
                    for price, qty in self.LINES
                ]
                lines.append(Command.create({"display_type": "line_note", "name": "Nota"}))
                with_text = self._doc(currency=currency, invoice_line_ids=lines, **self.AMOUNT)
                self.assertEqual(with_text.amount_untaxed, self._doc(currency=currency, **self.AMOUNT).amount_untaxed)


class TestDeductibleRulesCustomer(TestDeductibleRules):
    MOVE_TYPE = "out_invoice"


class TestDeductibleScope(DeductibleCase):
    """The company decides which documents offer the deductible."""

    def test_scope_matrix(self):
        matrix = {"vendor": (True, False), "customer": (False, True), "both": (True, True)}
        for scope, allowed in matrix.items():
            self.company.deductible_scope = scope
            for move_type, ok in zip(("in_invoice", "out_invoice"), allowed):
                with self.subTest(scope=scope, move_type=move_type):
                    self.assertEqual(self._doc(move_type=move_type).deductible_allowed, ok)
                    if ok:
                        self.assertTrue(self._doc(move_type=move_type, **self.PERCENT).is_deductible)
                    else:
                        with self.assertRaisesMsg(ValidationError, "not enabled for this company"):
                            self._doc(move_type=move_type, **self.PERCENT)

    def test_disabled_company_rejects_both_sides(self):
        self.company.use_deductible = False
        for move_type in ("in_invoice", "out_invoice"):
            self.assertFalse(self._doc(move_type=move_type).deductible_allowed)
            with self.assertRaisesMsg(ValidationError, "not enabled for this company"):
                self._doc(move_type=move_type, **self.PERCENT)


class TestDeductibleViewsAndTranslation(DeductibleCase):
    """Where the section sits in the form, the read-only amount column and the
    Spanish translation file."""

    def _arch(self):
        return self.env["account.move"].get_view(self.env.ref("account.view_move_form").id, "form")["arch"]

    def test_section_is_below_the_terms_and_reference_only_for_percentage(self):
        arch = self._arch()
        narration, first = arch.index('name="narration"'), arch.index('name="is_deductible"')
        self.assertTrue(narration < first < narration + 400)
        self.assertNotIn("is_deductible", arch[: arch.index('name="invoice_tab"')])
        reference = arch[arch.index('name="global_deductible_reference_amount"'):]
        self.assertIn("global_deductible_type != &#39;percent&#39;", reference[: reference.index("/>")].replace("'", "&#39;"))

    def test_line_amount_column_is_read_only_and_only_for_fixed_amount(self):
        arch = self._arch()
        self.assertRegex(
            arch,
            r'name="global_deductible_line_amount"[^>]*readonly="1"|readonly="1"[^>]*name="global_deductible_line_amount"',
        )
        self.assertIn("parent.global_deductible_type != 'amount'", arch)

    def test_spanish_translation_file_is_valid(self):
        with file_open("l10n_ve_deductible/i18n/es_VE.po", "rb") as po:
            entries = list(PoFileReader(po))
        terms = {entry["src"]: entry["value"] for entry in entries}
        self.assertTrue(all(entry["module"] == "l10n_ve_deductible" for entry in entries))
        self.assertEqual(terms["Deductibles"], "Deducibles")
        self.assertEqual(terms["Deductible Applies To"], "El deducible aplica a")
        self.assertTrue(all(terms.values()), "every term is translated")
