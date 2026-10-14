from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestRefundOriginValidation(TransactionCase):
    """Ticket #13965: a credit note (out_refund/in_refund) must not
    introduce a product absent from its origin invoice, nor credit more
    than what was invoiced for a given product."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tax = cls.env["account.tax"].create({
            "name": "IVA 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "sale",
        })
        cls.purchase_tax = cls.env["account.tax"].create({
            "name": "IVA Compra 16%",
            "amount": 16,
            "amount_type": "percent",
            "type_tax_use": "purchase",
        })
        cls.product_a = cls.env["product.product"].create({
            "name": "Producto A",
            "type": "service",
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Producto B",
            "type": "service",
        })
        cls.product_c = cls.env["product.product"].create({
            "name": "Producto C",
            "type": "service",
        })
        cls.product_storable = cls.env["product.product"].create({
            "name": "Producto Almacenable",
            "type": "consu",
        })
        cls.service_early_payment = cls.env["product.product"].create({
            "name": "Pronto Pago",
            "type": "service",
        })
        cls.partner = cls.env["res.partner"].create({"name": "Cliente de prueba"})
        cls.journal = cls.env["account.journal"].create({
            "name": "Diario de Ventas Refund Test",
            "code": "VRT",
            "type": "sale",
        })
        cls.purchase_journal = cls.env["account.journal"].create({
            "name": "Diario de Compras Refund Test",
            "code": "VRTP",
            "type": "purchase",
        })
        cls.income_account = cls.env["account.account"].create({
            "name": "Revenue Refund Test", "code": "4444442",
            "account_type": "income",
        })

    def _create_invoice_line(self, product, quantity=1, price_unit=100.0, tax=None):
        return Command.create({
            "product_id": product.id,
            "quantity": quantity,
            "price_unit": price_unit,
            "tax_ids": [Command.set((tax or self.tax).ids)],
        })

    def _create_invoice(self, lines, move_type="out_invoice", reversed_entry_id=False, journal=None):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": (journal or self.journal).id,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "invoice_line_ids": lines,
        }
        if reversed_entry_id:
            vals["reversed_entry_id"] = reversed_entry_id.id
        return self.env["account.move"].create(vals)
    def _post(self, move):
        # `_post()` directly: `action_post()` stops at the
        # l10n_ve_accountant confirmation wizard unless
        # `move_action_post_alert` is set, and the validation under test
        # runs in `_post()` anyway.
        move._post(soft=False)
        return move

    def _create_refund(self, lines, origin, move_type="out_refund", journal=None):
        return self._create_invoice(
            lines, move_type=move_type, reversed_entry_id=origin, journal=journal
        )

    def _posted_invoice(self, *lines):
        return self._post(self._create_invoice(list(lines)))

    def test_credit_note_with_same_product_and_lower_amount_is_allowed(self):
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._post(self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 50.0)], invoice
        ))
        self.assertEqual(credit_note.state, "posted")
        self.assertEqual(credit_note.invoice_line_ids.product_id, self.product_a)
        self.assertEqual(credit_note.amount_untaxed, 50.0)

    def test_credit_note_with_foreign_product_is_blocked(self):
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._create_refund(
            [self._create_invoice_line(self.product_storable, 1, 10.0)], invoice
        )
        with self.assertRaises(ValidationError):
            self._post(credit_note)

    def test_credit_note_with_foreign_service_product_is_allowed(self):
        """Ticket #81674: financial concepts that never appear on the
        original invoice (early payment, commercial discount, exchange
        difference) are service products and must not be blocked by the
        origin-membership check, unlike storable/consumable products."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._post(self._create_refund(
            [self._create_invoice_line(self.service_early_payment, 1, 10.0)], invoice
        ))
        self.assertEqual(credit_note.invoice_line_ids.product_id, self.service_early_payment)

    def test_credit_note_with_foreign_service_product_cannot_exceed_origin_total(self):
        """A foreign service line has no per-product cap, but it must
        still respect the origin's grand total."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._create_refund(
            [self._create_invoice_line(self.service_early_payment, 1, 150.0)], invoice
        )
        with self.assertRaises(ValidationError):
            self._post(credit_note)

    def test_credit_note_with_foreign_service_product_exactly_at_origin_total_is_allowed(self):
        """The boundary case: a foreign service line that credits exactly
        the origin's total (not a cent more) must be allowed."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._post(self._create_refund(
            [self._create_invoice_line(self.service_early_payment, 1, 100.0)], invoice
        ))
        self.assertEqual(credit_note.amount_untaxed, 100.0)

    def test_credit_note_mixing_origin_product_and_foreign_service_cannot_exceed_origin_total(self):
        """A credit note combining a same-origin product line with a
        foreign service line must respect the origin's grand total across
        both lines together, not just the per-product cap on the first
        one."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._create_refund(
            [
                self._create_invoice_line(self.product_a, 1, 60.0),
                self._create_invoice_line(self.service_early_payment, 1, 60.0),
            ],
            invoice,
        )
        with self.assertRaises(ValidationError):
            self._post(credit_note)

    def test_credit_note_mixing_origin_product_and_foreign_service_within_origin_total_is_allowed(self):
        """Same combination as above, but staying within the origin's
        grand total, so it must be allowed."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._post(self._create_refund(
            [
                self._create_invoice_line(self.product_a, 1, 60.0),
                self._create_invoice_line(self.service_early_payment, 1, 30.0),
            ],
            invoice,
        ))
        self.assertEqual(credit_note.amount_untaxed, 90.0)

    def test_credit_note_with_multiple_foreign_service_products_cannot_exceed_origin_total(self):
        """Several distinct foreign service products on the same credit
        note must have their amounts summed for the grand-total check,
        not evaluated independently of each other."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._create_refund(
            [
                self._create_invoice_line(self.service_early_payment, 1, 60.0),
                self._create_invoice_line(self.product_c, 1, 60.0),
            ],
            invoice,
        )
        with self.assertRaises(ValidationError):
            self._post(credit_note)

    def test_cumulative_credit_notes_with_foreign_service_cannot_exceed_origin_total(self):
        """A first credit note against a normal product line uses up part
        of the origin's total; a second credit note with only a foreign
        service line must still be capped by what's left, not treated as
        starting from zero."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        self._post(self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 70.0)], invoice
        ))
        second_credit_note = self._create_refund(
            [self._create_invoice_line(self.service_early_payment, 1, 40.0)], invoice
        )
        with self.assertRaises(ValidationError):
            self._post(second_credit_note)

    def test_credit_note_line_without_product_is_blocked(self):
        """A manual description line has nothing to match against the
        origin, so it must not be allowed to slip past both checks.

        l10n_ve_accountant's `_check_product_id` already rejects such a
        line when created through `invoice_line_ids`, but not when the
        product is removed by a write on the line itself -- that's the
        path left for this validation to catch at posting time."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 50.0)], invoice
        )
        credit_note.invoice_line_ids.write({
            "product_id": False,
            "name": "Ajuste manual",
            "account_id": self.income_account.id,
            "price_unit": 1000000.0,
        })
        with self.assertRaisesRegex(ValidationError, "must have a product"):
            self._post(credit_note)

    def test_credit_note_with_a_subsection_is_allowed(self):
        """`line_subsection` is the display_type Odoo 19 added to the layout
        family, and it was missing from `product_line_types` in
        `_check_refund_against_origin()`.

        Without it the subsection was read as a product line to credit and
        fell into "Every product line on this credit note must have a
        product" -- the very path
        `test_credit_note_line_without_product_is_blocked` asserts, which is
        why the change was invisible to this file. A layout line has no
        product and nothing to match against the origin by design, so it has
        to be ignored, not blocked.
        """
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))

        refund = self._post(self._create_refund(
            [
                Command.create({
                    "display_type": "line_section",
                    "name": "Estudios",
                }),
                Command.create({
                    "display_type": "line_subsection",
                    "name": "Primera etapa",
                }),
                self._create_invoice_line(self.product_a, 1, 100.0),
                Command.create({
                    "display_type": "line_note",
                    "name": "Nota",
                }),
            ],
            invoice,
        ))

        self.assertEqual(refund.state, "posted", "the credit note with a subsection was rejected")
        self.assertTrue(
            refund.invoice_line_ids.filtered(
                lambda l: l.display_type == "line_subsection"
            ),
            "fixture is broken: no subsection survived on the credit note, so "
            "this test would pass without exercising the guard",
        )

    def test_credit_note_exceeding_origin_amount_is_blocked(self):
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 150.0)], invoice
        )
        with self.assertRaises(ValidationError):
            self._post(credit_note)

    def test_vendor_credit_note_in_refund_is_also_validated(self):
        """The validation covers both out_refund and in_refund -- a
        vendor bill's credit note must respect the same rules."""
        bill = self._create_invoice(
            [self._create_invoice_line(self.product_a, 1, 100.0, tax=self.purchase_tax)],
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        self._post(bill)
        credit_note = self._create_refund(
            [self._create_invoice_line(self.product_storable, 1, 10.0, tax=self.purchase_tax)],
            bill,
            move_type="in_refund",
            journal=self.purchase_journal,
        )
        with self.assertRaises(ValidationError):
            self._post(credit_note)

    def test_credit_note_without_origin_skips_validation(self):
        """A credit note created with no reversed_entry_id at all (e.g.
        a standalone credit note from the Accounting menu) is not tied
        to any invoice, so there is nothing to validate it against --
        this is a known, intentional gap, not covered by this ticket."""
        credit_note = self._post(self._create_invoice(
            [self._create_invoice_line(self.product_c, 1, 999999.0)],
            move_type="out_refund",
        ))
        self.assertEqual(credit_note.state, "posted")

    def test_bypass_context_allows_foreign_product(self):
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_note = self._create_refund(
            [self._create_invoice_line(self.product_storable, 1, 999.0)], invoice
        )
        # The key must be active when the credit note is POSTED -- that's
        # where the validation runs now.
        self._post(credit_note.with_context(l10n_ve_skip_refund_origin_validation=True))
        self.assertEqual(credit_note.state, "posted")

    def test_cumulative_credit_notes_cannot_exceed_origin_amount(self):
        """Two credit notes, each individually within the origin's
        amount, must not be allowed to jointly exceed it."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        self._post(self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 60.0)], invoice
        ))
        second_credit_note = self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 60.0)], invoice
        )
        with self.assertRaises(ValidationError):
            self._post(second_credit_note)

    def test_credit_notes_posted_together_cannot_jointly_exceed_origin_amount(self):
        """Two drafts posted in the same `_post()` batch are not
        `posted` yet when the check runs -- they must still count
        against each other."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        credit_notes = self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 60.0)], invoice
        ) | self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 60.0)], invoice
        )
        with self.assertRaises(ValidationError):
            self._post(credit_notes)

    def test_forgotten_draft_credit_note_does_not_block_posting_another(self):
        """A draft that alone exceeds the cap is only checked when it is
        itself posted -- it must not block posting a valid credit note."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 1, 100.0))
        self._create_refund([self._create_invoice_line(self.product_a, 1, 100.0)], invoice)
        credit_note = self._post(self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 30.0)], invoice
        ))
        self.assertEqual(credit_note.state, "posted")

    def test_line_write_over_cap_is_only_blocked_at_posting(self):
        """Editing a draft credit note's line above the cap (or to a
        foreign product) is allowed while it is a draft; posting it is
        what must fail."""
        invoice = self._posted_invoice(
            self._create_invoice_line(self.product_a, 1, 100.0),
            self._create_invoice_line(self.product_b, 1, 100.0),
        )
        over_cap = self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 50.0)], invoice
        )
        over_cap.invoice_line_ids[0].write({"price_unit": 150.0})
        with self.assertRaises(ValidationError):
            self._post(over_cap)

        foreign = self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 50.0)], invoice
        )
        foreign.invoice_line_ids[0].write({"product_id": self.product_storable.id})
        with self.assertRaises(ValidationError):
            self._post(foreign)

    def test_second_credit_note_from_reversal_wizard_is_editable_before_posting(self):
        """Odoo 17+ has no "partial refund" button: "Reverse" copies the
        full invoice into a draft the user reduces before posting. With a
        partial credit note already posted, that full-amount draft must
        still be created (the cap is only enforced at posting), and post
        fine once reduced."""
        invoice = self._posted_invoice(self._create_invoice_line(self.product_a, 10, 80.0))
        self._post(self._create_refund(
            [self._create_invoice_line(self.product_a, 1, 80.0)], invoice
        ))

        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({
            "reason": "Pronto pago",
            "journal_id": invoice.journal_id.id,
        })
        wizard.refund_moves()
        draft = wizard.new_move_ids
        self.assertEqual(draft.state, "draft")
        self.assertEqual(draft.invoice_line_ids.quantity, 10)

        with self.assertRaises(ValidationError):
            self._post(draft)

        draft.invoice_line_ids.write({"quantity": 2})
        self._post(draft)
        self.assertEqual(draft.state, "posted")
