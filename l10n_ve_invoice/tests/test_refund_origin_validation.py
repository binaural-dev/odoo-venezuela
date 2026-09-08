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

    def test_credit_note_with_same_product_and_lower_amount_is_allowed(self):
        invoice = self._create_invoice([self._create_invoice_line(self.product_a, 1, 100.0)])
        invoice.action_post()
        # No ValidationError expected: this is exactly the case the
        # constrains must let through. Whether the move can later reach
        # "posted" depends on unrelated accounting setup, not on this
        # validation, so we don't assert the state here.
        credit_note = self._create_invoice(
            [self._create_invoice_line(self.product_a, 1, 50.0)],
            move_type="out_refund",
            reversed_entry_id=invoice,
        )
        self.assertEqual(credit_note.invoice_line_ids.product_id, self.product_a)
        self.assertEqual(credit_note.amount_untaxed, 50.0)

    def test_credit_note_with_foreign_product_is_blocked(self):
        invoice = self._create_invoice([self._create_invoice_line(self.product_a, 1, 100.0)])
        invoice.action_post()
        with self.assertRaises(ValidationError):
            self._create_invoice(
                [self._create_invoice_line(self.product_b, 1, 10.0)],
                move_type="out_refund",
                reversed_entry_id=invoice,
            )

    def test_credit_note_line_without_product_is_blocked(self):
        """A manual description line has nothing to match against the
        origin, so it must not be allowed to slip past both checks."""
        invoice = self._create_invoice([self._create_invoice_line(self.product_a, 1, 100.0)])
        invoice.action_post()
        with self.assertRaises(ValidationError):
            self._create_invoice(
                [Command.create({
                    "name": "Ajuste manual",
                    "account_id": self.income_account.id,
                    "quantity": 1,
                    "price_unit": 1000000.0,
                    "tax_ids": [Command.set(self.tax.ids)],
                })],
                move_type="out_refund",
                reversed_entry_id=invoice,
            )

    def test_credit_note_exceeding_origin_amount_is_blocked(self):
        invoice = self._create_invoice([self._create_invoice_line(self.product_a, 1, 100.0)])
        invoice.action_post()
        with self.assertRaises(ValidationError):
            self._create_invoice(
                [self._create_invoice_line(self.product_a, 1, 150.0)],
                move_type="out_refund",
                reversed_entry_id=invoice,
            )

    def test_vendor_credit_note_in_refund_is_also_validated(self):
        """The constrains covers both out_refund and in_refund -- a
        vendor bill's credit note must respect the same rules."""
        bill = self._create_invoice(
            [self._create_invoice_line(self.product_a, 1, 100.0, tax=self.purchase_tax)],
            move_type="in_invoice",
            journal=self.purchase_journal,
        )
        bill.action_post()
        with self.assertRaises(ValidationError):
            self._create_invoice(
                [self._create_invoice_line(self.product_b, 1, 10.0, tax=self.purchase_tax)],
                move_type="in_refund",
                reversed_entry_id=bill,
                journal=self.purchase_journal,
            )

    def test_credit_note_without_origin_skips_validation(self):
        """A credit note created with no reversed_entry_id at all (e.g.
        a standalone credit note from the Accounting menu) is not tied
        to any invoice, so there is nothing to validate it against --
        this is a known, intentional gap, not covered by this ticket."""
        credit_note = self._create_invoice(
            [self._create_invoice_line(self.product_c, 1, 999999.0)],
            move_type="out_refund",
        )
        self.assertTrue(credit_note.id)

    def test_bypass_context_allows_foreign_product(self):
        invoice = self._create_invoice([self._create_invoice_line(self.product_a, 1, 100.0)])
        invoice.action_post()
        # The record must be created with the bypass context already
        # active for the constrains to see it (a later with_context()
        # on an existing recordset would be too late).
        credit_note = self.env["account.move"].with_context(
            l10n_ve_skip_refund_origin_validation=True
        ).create({
            "move_type": "out_refund",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": fields.Date.today(),
            "invoice_date_display": fields.Date.today(),
            "reversed_entry_id": invoice.id,
            "invoice_line_ids": [self._create_invoice_line(self.product_b, 1, 999.0)],
        })
        self.assertTrue(credit_note.id)

    def test_cumulative_credit_notes_cannot_exceed_origin_amount(self):
        """Two credit notes, each individually within the origin's
        amount, must not be allowed to jointly exceed it."""
        invoice = self._create_invoice([self._create_invoice_line(self.product_a, 1, 100.0)])
        invoice.action_post()

        first_credit_note = self._create_invoice(
            [self._create_invoice_line(self.product_a, 1, 60.0)],
            move_type="out_refund",
            reversed_entry_id=invoice,
        )
        self.assertTrue(first_credit_note.id)

        with self.assertRaises(ValidationError):
            self._create_invoice(
                [self._create_invoice_line(self.product_a, 1, 60.0)],
                move_type="out_refund",
                reversed_entry_id=invoice,
            )

    def test_line_write_to_foreign_product_is_blocked(self):
        """A write() directly on the line (not through the parent
        move's invoice_line_ids) must trigger the same validation --
        the parent's constrains does not fire on a plain line write()."""
        invoice = self._create_invoice([
            self._create_invoice_line(self.product_a, 1, 100.0),
            self._create_invoice_line(self.product_b, 1, 100.0),
        ])
        invoice.action_post()
        credit_note = self._create_invoice(
            [self._create_invoice_line(self.product_a, 1, 50.0)],
            move_type="out_refund",
            reversed_entry_id=invoice,
        )
        line = credit_note.invoice_line_ids[0]
        with self.assertRaises(ValidationError):
            line.write({"product_id": self.product_c.id})

    def test_line_write_raising_amount_over_cap_is_blocked(self):
        """Same line-level trigger, but for the amount check instead of
        the foreign-product check."""
        invoice = self._create_invoice([self._create_invoice_line(self.product_a, 1, 100.0)])
        invoice.action_post()
        credit_note = self._create_invoice(
            [self._create_invoice_line(self.product_a, 1, 50.0)],
            move_type="out_refund",
            reversed_entry_id=invoice,
        )
        line = credit_note.invoice_line_ids[0]
        with self.assertRaises(ValidationError):
            line.write({"price_unit": 150.0})
