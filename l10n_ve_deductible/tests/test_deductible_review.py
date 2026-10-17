from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open
from odoo.tools.translate import PoFileReader

from .common import AssertMixin, ensure_ve_base, set_usd_rate


@tagged("post_install", "-at_install", "l10n_ve_deductible")
class TestDeductibleReviewCases(AssertMixin, TransactionCase):
    """Cases raised in the code review: credit notes, copies, sections/notes,
    price-included taxes, disabled setting, rate/date changes, reports, i18n
    and the install hook. Base VEF / alternate USD, recent market rate."""

    RATE = 0.00116565386887513
    LINES = [(10.3333, 3), (7.1249, 7), (0.9999, 13), (123.4567, 1), (3.3333, 9)]
    DEDUCTIBLE_AMOUNT = {"global_deductible_type": "amount", "global_deductible_amount": 77.77}
    DEDUCTIBLES = (
        {"global_deductible_type": "percent", "global_deductible_percent": 12.5},
        {"global_deductible_type": "amount", "global_deductible_amount": 77.77},
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_ve_base(cls.env)
        cls.env.ref("product.decimal_price").digits = 4
        cls.vef, cls.usd = cls.env.ref("base.VEF"), cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.company.write({"use_deductible": True, "discount_type": "percent"})
        set_usd_rate(cls.env, cls.RATE)
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Review"})
        cls.exempt = cls.env["account.tax"].create(
            {"name": "Ex Rev", "amount_type": "percent", "amount": 0.0, "type_tax_use": "purchase"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Prod Rev", "supplier_taxes_id": [Command.set(cls.exempt.ids)]}
        )

    def _line(self, price, qty, tax=None, **extra):
        return Command.create(
            {"product_id": self.product.id, "name": "L", "quantity": qty,
             "price_unit": price, "tax_ids": [Command.set((tax or self.exempt).ids)], **extra}
        )

    def _bill(self, currency=None, lines=None, **vals):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "currency_id": (currency or self.usd).id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": lines or [self._line(p, q) for p, q in self.LINES],
                **vals,
            }
        )

    def _each(self):
        for method in ("round_per_line", "round_globally"):
            for currency in (self.usd, self.vef):
                for deductible in self.DEDUCTIBLES:
                    self.company.tax_calculation_rounding_method = method
                    yield method, currency, deductible

    def _reverse(self, bill, cancel=True):
        """Credit note through the standard wizard: `cancel` = reverse and
        cancel (posted, reconciled); otherwise a draft credit note."""
        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=bill.ids
        ).create({"journal_id": bill.journal_id.id, "date": fields.Date.today()})
        wizard.modify_moves() if cancel else wizard.refund_moves()
        return bill.reversal_move_ids

    def test_credit_note_of_a_deductible_bill(self):
        for method, currency, deductible in self._each():
            with self.subTest(method=method, currency=currency.name, **deductible):
                bill = self._bill(currency, is_deductible=True, **deductible)
                bill.action_post()
                refund = self._reverse(bill)
                self.assertEqual(refund.move_type, "in_refund")
                self.assertTrue(refund.is_deductible)
                self.assertEqual(refund.state, "posted")
                self.assertEqual(refund.amount_total, bill.amount_total)
                self.assertEqual(refund.amount_untaxed, bill.amount_untaxed)
                self.assertEqual(
                    refund.invoice_line_ids.mapped("price_subtotal"),
                    bill.invoice_line_ids.mapped("price_subtotal"),
                )
                self.assertEqual(bill.amount_residual, 0.0, "the credit note cancels the bill")

    def test_draft_credit_note_keeps_the_deductible_and_can_be_edited(self):
        bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[0])
        bill.action_post()
        refund = self._reverse(bill, cancel=False)
        self.assertEqual(refund.state, "draft")
        self.assertTrue(refund.is_deductible)
        self.assertEqual(refund.global_deductible_percent, 12.5)
        refund.invoice_line_ids[0].quantity = 1
        self.assertLess(refund.amount_total, bill.amount_total)
        refund.action_post()
        with self.assertRaisesMsg(UserError, "draft bills"):
            refund.write({"global_deductible_percent": 5.0})

    def test_credit_note_of_a_plain_bill_is_not_deductible(self):
        bill = self._bill(self.usd)
        bill.action_post()
        refund = self._reverse(bill)
        self.assertFalse(refund.is_deductible)

    def _debit_note(self, bill, copy_lines):
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=bill.ids
        ).create({"copy_lines": copy_lines, "date": fields.Date.today()})
        action = wizard.create_debit()
        return self.env["account.move"].browse(action["res_id"])

    def test_debit_note_with_copied_lines_keeps_the_deductible(self):
        for method, currency, deductible in self._each():
            with self.subTest(method=method, currency=currency.name, **deductible):
                bill = self._bill(currency, is_deductible=True, **deductible)
                bill.action_post()
                note = self._debit_note(bill, copy_lines=True)
                self.assertEqual(note.debit_origin_id, bill)
                self.assertTrue(note.is_deductible)
                self.assertEqual(note.global_deductible_type, bill.global_deductible_type)
                self.assertEqual(note.amount_untaxed, bill.amount_untaxed)
                self.assertEqual(note.amount_total_signed, bill.amount_total_signed)
                self.assertEqual(note.invoice_line_ids.mapped("balance"),
                                 bill.invoice_line_ids.mapped("balance"))

    def test_debit_note_without_lines_starts_plain(self):
        bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[1])
        bill.action_post()
        note = self._debit_note(bill, copy_lines=False)
        self.assertFalse(note.is_deductible)
        self.assertFalse(note.invoice_line_ids)

    def test_reverse_and_modify_keeps_the_deductible_on_the_replacement(self):
        for method, currency, deductible in self._each():
            with self.subTest(method=method, currency=currency.name, **deductible):
                bill = self._bill(currency, is_deductible=True, **deductible)
                bill.action_post()
                wizard = self.env["account.move.reversal"].with_context(
                    active_model="account.move", active_ids=bill.ids
                ).create({"journal_id": bill.journal_id.id, "date": fields.Date.today()})
                action = wizard.modify_moves()
                replacement = self.env["account.move"].browse(action["res_id"])
                refund = bill.reversal_move_ids
                self.assertTrue(refund.is_deductible)
                self.assertEqual(refund.amount_total, bill.amount_total)
                self.assertEqual(replacement.state, "draft")
                self.assertTrue(replacement.is_deductible)
                self.assertEqual(replacement.global_deductible_type, bill.global_deductible_type)
                self.assertEqual(replacement.amount_untaxed, bill.amount_untaxed)
                if deductible["global_deductible_type"] == "amount":
                    self.assertEqual(
                        round(sum(replacement.invoice_line_ids.mapped("global_deductible_line_amount")), 2),
                        77.77,
                    )

    def test_duplicate_does_not_carry_the_deductible(self):
        bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[1])
        copy = bill.copy()
        self.assertFalse(copy.is_deductible)
        self.assertFalse(any(copy.invoice_line_ids.mapped("global_deductible_discount_percent")))
        self.assertEqual(copy.amount_untaxed, self._bill(self.usd).amount_untaxed)

    def test_sections_and_notes_are_ignored(self):
        for method, currency, deductible in self._each():
            with self.subTest(method=method, currency=currency.name, **deductible):
                lines = [Command.create({"display_type": "line_section", "name": "Sección"})]
                for p, q in self.LINES:
                    lines.append(self._line(p, q))
                lines.append(Command.create({"display_type": "line_note", "name": "Nota"}))
                bill = self._bill(currency, lines=lines, is_deductible=True, **deductible)
                plain_lines = self._bill(
                    currency, is_deductible=True, **deductible
                )
                self.assertEqual(bill.amount_untaxed, plain_lines.amount_untaxed)
                self.assertEqual(bill.amount_total_signed, plain_lines.amount_total_signed)

    def test_taxed_line_added_to_a_deductible_bill(self):
        general = self.env["account.tax"].create(
            {"name": "IVA Rev", "amount_type": "percent", "amount": 16.0, "type_tax_use": "purchase"}
        )
        bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[0])
        with self.assertRaisesMsg(ValidationError, "exempt tax"):
            bill.write({"invoice_line_ids": [self._line(5.0, 1, tax=general)]})

    def test_price_included_exempt_tax_matches_native_discount(self):
        """A price-included exempt tax keeps the deductible in the journal
        items (l10n_ve_accountant rebuilds those lines by hand)."""
        included = self.env["account.tax"].create(
            {"name": "Ex incl", "amount_type": "percent", "amount": 0.0,
             "type_tax_use": "purchase", "price_include_override": "tax_included"}
        )
        self.assertTrue(included.price_include)
        lines = [(100.0, 2), (33.3333, 3)]
        for method, currency, _deductible in self._each():
            with self.subTest(method=method, currency=currency.name):
                mine = self._bill(
                    currency, lines=[self._line(p, q, tax=included) for p, q in lines],
                    is_deductible=True, global_deductible_type="percent",
                    global_deductible_percent=12.5,
                )
                native = self._bill(
                    currency,
                    lines=[self._line(p, q, tax=included, discount=12.5) for p, q in lines],
                )
                self.assertEqual(mine.amount_total, native.amount_total)
                self.assertEqual(mine.amount_total_signed, native.amount_total_signed)
                self.assertEqual(mine.invoice_line_ids.mapped("balance"),
                                 native.invoice_line_ids.mapped("balance"))
                self.assertEqual(mine.invoice_line_ids.mapped("price_subtotal"),
                                 native.invoice_line_ids.mapped("price_subtotal"))

    def test_setting_disabled_blocks_new_deductible_bills(self):
        self.company.use_deductible = False
        with self.assertRaisesMsg(ValidationError, "not enabled for this company"):
            self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[0])
        self.assertFalse(self._bill(self.usd).tax_totals.get("is_deductible"))

    def test_rate_and_date_change_with_active_deductible(self):
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        set_usd_rate(self.env, 0.001166853246500782, yesterday)
        for method in ("round_per_line", "round_globally"):
            with self.subTest(method=method):
                self.company.tax_calculation_rounding_method = method
                bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[1])
                bill.invoice_date = yesterday
                fresh = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[1],
                                   invoice_date=yesterday)
                self.assertEqual(bill.amount_total_signed, fresh.amount_total_signed)
                self.assertEqual(bill.invoice_line_ids.mapped("balance"),
                                 fresh.invoice_line_ids.mapped("balance"))
                bill.invoice_date = fields.Date.today()
                today_bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[1])
                self.assertEqual(bill.amount_total_signed, today_bill.amount_total_signed)

    def test_detailed_amounts_add_up(self):
        for method, currency, deductible in self._each():
            with self.subTest(method=method, currency=currency.name, **deductible):
                bill = self._bill(currency, is_deductible=True, **deductible)
                details = bill.detailed_amounts
                gross = sum(l.price_unit * l.quantity for l in bill.invoice_line_ids)
                self.assertEqual(details["gross_amount"], gross)
                self.assertEqual(
                    round(details["gross_amount"] - details["discount_amount"], 2),
                    round(sum(bill.invoice_line_ids.mapped("price_subtotal")), 2),
                )
                self.assertGreater(details["discount_amount"], 0)

    def test_line_amounts_add_up_to_the_entered_amount(self):
        for method, currency, deductible in self._each():
            if deductible["global_deductible_type"] != "amount":
                continue
            with self.subTest(method=method, currency=currency.name):
                bill = self._bill(currency, is_deductible=True, **deductible)
                lines = bill.invoice_line_ids
                amounts = lines.mapped("global_deductible_line_amount")
                self.assertEqual(round(sum(amounts), 4), 77.77)
                self.assertTrue(all(0 < a for a in amounts))
                for line in lines:
                    gross = line.price_unit * line.quantity
                    self.assertLess(line.global_deductible_line_amount, gross)
                    self.assertEqual(
                        line.global_deductible_discount_percent,
                        (line.global_deductible_line_amount / gross) * 100.0,
                    )
                lines[0].price_unit = 55.5555
                bill.write({"invoice_line_ids": [self._line(19.9876, 4)]})
                self.assertEqual(
                    round(sum(bill.invoice_line_ids.mapped("global_deductible_line_amount")), 4),
                    77.77,
                )

    def test_line_amount_only_in_fixed_amount_mode(self):
        pct = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLES[0])
        self.assertFalse(any(pct.invoice_line_ids.mapped("global_deductible_line_amount")))
        plain = self._bill(self.usd)
        self.assertFalse(any(plain.invoice_line_ids.mapped("global_deductible_line_amount")))
        bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLE_AMOUNT)
        bill.is_deductible = False
        self.assertFalse(any(bill.invoice_line_ids.mapped("global_deductible_line_amount")))

    def test_line_amount_cannot_be_written_by_hand(self):
        bill = self._bill(self.usd, is_deductible=True, **self.DEDUCTIBLE_AMOUNT)
        with self.assertRaisesMsg(ValidationError, "must add up to the deductible amount"):
            bill.invoice_line_ids[0].write({"global_deductible_line_amount": 1.0})

    def test_section_is_below_the_terms_and_reference_only_for_percentage(self):
        """The section sits right after `narration` (Términos y condiciones) of
        the lines tab, not in the header; the reference amount is only shown
        for the percentage type."""
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        narration = arch.index('name="narration"')
        first = arch.index('name="is_deductible"')
        self.assertLess(narration, first)
        self.assertLess(first - narration, 400)
        header = arch[: arch.index('name="invoice_tab"')]
        self.assertNotIn("is_deductible", header)
        reference = arch[arch.index('name="global_deductible_reference_amount"'):]
        reference = reference[: reference.index("/>")]
        self.assertIn("global_deductible_type != &#39;percent&#39;", reference.replace("'", "&#39;"))

    def test_line_amount_column_is_read_only_and_only_for_fixed_amount(self):
        arch = self.env["account.move"].get_view(
            self.env.ref("account.view_move_form").id, "form"
        )["arch"]
        self.assertIn("global_deductible_line_amount", arch)
        self.assertRegex(
            arch,
            r'name="global_deductible_line_amount"[^>]*readonly="1"|readonly="1"[^>]*name="global_deductible_line_amount"',
        )
        self.assertIn("parent.global_deductible_type != 'amount'", arch)

    def test_spanish_translation_file_is_valid(self):
        with file_open("l10n_ve_deductible/i18n/es_VE.po", "rb") as po:
            entries = list(PoFileReader(po))
        terms = {e["src"]: e["value"] for e in entries}
        self.assertTrue(entries)
        self.assertTrue(all(e["module"] == "l10n_ve_deductible" for e in entries))
        self.assertEqual(terms["Deductibles"], "Deducibles")
        self.assertEqual(terms["Subtotal without deductible"], "Subtotal sin deducible")
