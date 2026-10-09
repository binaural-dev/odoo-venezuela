from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestFutureDateActionPost(TransactionCase):
    """Ninguna de las fechas (`invoice_date`, `invoice_date_display`, `date`)
    de una factura, nota de crédito o nota de débito -- de venta o de compra --
    puede ser posterior a hoy al confirmarla (`action_post`)."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")

        self.partner = self.env["res.partner"].create({"name": "Test FD Partner"})

        self.account_revenue = self.env["account.account"].create(
            {
                "name": "Revenue FD",
                "code": "981001",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.account_expense = self.env["account.account"].create(
            {
                "name": "Expense FD",
                "code": "681001",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.journal_sale = self.env["account.journal"].create(
            {
                "name": "Sale FD Journal",
                "type": "sale",
                "code": "FDSJ",
                "company_id": self.company.id,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.journal_purchase = self.env["account.journal"].create(
            {
                "name": "Purchase FD Journal",
                "type": "purchase",
                "code": "FDPJ",
                "company_id": self.company.id,
                "default_account_id": self.account_expense.id,
            }
        )
        self.tax_sale = self.env["account.tax"].create(
            {
                "name": "IVA 16% FD Sale",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
            }
        )
        self.tax_purchase = self.env["account.tax"].create(
            {
                "name": "IVA 16% FD Purchase",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product FD",
                "type": "service",
                "list_price": 100,
                "taxes_id": [(6, 0, [self.tax_sale.id])],
                "supplier_taxes_id": [(6, 0, [self.tax_purchase.id])],
            }
        )

    def _create_move(self, move_type, journal, tax, **date_overrides):
        today = fields.Date.today()
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "journal_id": journal.id,
            "invoice_date": today,
            "invoice_date_display": today,
            "date": today,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 100,
                        "tax_ids": [(6, 0, [tax.id])],
                    },
                )
            ],
        }
        vals.update(date_overrides)
        return self.env["account.move"].create(vals)

    def test_invoice_today_posts_ok(self):
        invoice = self._create_move("out_invoice", self.journal_sale, self.tax_sale)
        # `move_action_post_alert`: l10n_ve_accountant intercepta
        # action_post() de out_invoice/out_refund con un wizard de
        # confirmación salvo que este contexto ya venga marcado -- nada
        # que ver con el guard de fecha futura que se está probando aquí.
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

    def test_vendor_bill_today_posts_ok(self):
        bill = self._create_move("in_invoice", self.journal_purchase, self.tax_purchase)
        bill.action_post()
        self.assertEqual(bill.state, "posted")

    def test_invoice_date_in_future_blocks_post(self):
        future = fields.Date.today() + timedelta(days=1)
        invoice = self._create_move(
            "out_invoice", self.journal_sale, self.tax_sale, invoice_date=future
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            invoice.action_post()

    def test_invoice_date_display_in_future_blocks_post(self):
        future = fields.Date.today() + timedelta(days=1)
        invoice = self._create_move(
            "out_invoice",
            self.journal_sale,
            self.tax_sale,
            invoice_date_display=future,
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            invoice.action_post()

    def test_accounting_date_in_future_blocks_post(self):
        future = fields.Date.today() + timedelta(days=1)
        invoice = self._create_move(
            "out_invoice", self.journal_sale, self.tax_sale, date=future
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            invoice.action_post()

    def test_credit_note_date_in_future_blocks_post(self):
        future = fields.Date.today() + timedelta(days=1)
        credit_note = self._create_move(
            "out_refund", self.journal_sale, self.tax_sale, invoice_date=future
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            credit_note.action_post()

    def test_vendor_bill_date_in_future_blocks_post(self):
        future = fields.Date.today() + timedelta(days=1)
        bill = self._create_move(
            "in_invoice",
            self.journal_purchase,
            self.tax_purchase,
            invoice_date=future,
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            bill.action_post()

    def test_vendor_refund_date_in_future_blocks_post(self):
        future = fields.Date.today() + timedelta(days=1)
        refund = self._create_move(
            "in_refund",
            self.journal_purchase,
            self.tax_purchase,
            invoice_date=future,
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            refund.action_post()

    def test_sale_receipt_date_in_future_blocks_post(self):
        """`out_receipt` no está en la lista explícita de 4 move_type, pero
        tampoco es 'entry' -- `is_invoice(include_receipts=True)` lo cubre."""
        future = fields.Date.today() + timedelta(days=1)
        receipt = self._create_move(
            "out_receipt", self.journal_sale, self.tax_sale, invoice_date=future
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            receipt.action_post()

    def test_purchase_receipt_date_in_future_blocks_post(self):
        future = fields.Date.today() + timedelta(days=1)
        receipt = self._create_move(
            "in_receipt",
            self.journal_purchase,
            self.tax_purchase,
            invoice_date=future,
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            receipt.action_post()

    def test_journal_entry_with_future_date_is_not_blocked(self):
        """'entry' (asiento contable puro) es el único move_type que el
        guard deja pasar sin revisar sus fechas."""
        future = fields.Date.today() + timedelta(days=1)
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.journal_sale.id,
                "date": future,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_revenue.id,
                            "debit": 100,
                            "credit": 0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": self.account_expense.id,
                            "debit": 0,
                            "credit": 100,
                        },
                    ),
                ],
            }
        )
        entry.action_post()  # No debe lanzar excepción
        self.assertEqual(entry.state, "posted")

    def test_draft_with_future_date_can_still_be_saved(self):
        """Guardar en borrador con fecha futura no debe bloquear -- solo
        `action_post` lo hace."""
        future = fields.Date.today() + timedelta(days=1)
        invoice = self._create_move(
            "out_invoice", self.journal_sale, self.tax_sale, invoice_date=future
        )
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.invoice_date, future)

    def test_debit_note_inherits_future_date_guard(self):
        """Una nota de débito es un `account.move` normal con
        `debit_origin_id`: el mismo `action_post` la cubre sin cambios
        adicionales."""
        invoice = self._create_move("out_invoice", self.journal_sale, self.tax_sale)
        invoice.with_context(move_action_post_alert=True).action_post()

        future = fields.Date.today() + timedelta(days=1)
        debit_note = invoice.copy(
            {
                "debit_origin_id": invoice.id,
                "invoice_date_display": future,
            }
        )
        with self.assertRaisesRegex(ValidationError, "cannot be later than today"):
            debit_note.action_post()
