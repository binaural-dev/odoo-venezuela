from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestVendorCorrelativeWithRef(TransactionCase):
    """Vendor bills from a fiscal machine may repeat the control number
    across different bills of the same vendor. Only the same vendor + same
    invoice number (``name``) + same control number is a duplicate, and it
    must be blocked when the document is confirmed, whatever the order in
    which the number was typed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.currency_id = cls.env.ref("base.VEF")
        cls.company.foreign_currency_id = cls.env.ref("base.USD")
        usd = cls.env.ref("base.USD")
        Rate = cls.env["res.currency.rate"]
        if not Rate.search_count(
            [("name", "=", fields.Date.today()), ("currency_id", "=", usd.id),
             ("company_id", "=", cls.company.id)]
        ):
            Rate.create(
                {"name": fields.Date.today(), "currency_id": usd.id,
                 "inverse_company_rate": 500.0, "company_id": cls.company.id}
            )
        Account = cls.env["account.account"]
        company_ids = [(6, 0, [cls.company.id])]
        cls.account_expense = Account.create(
            {"name": "Expense VCR", "code": "991003", "account_type": "expense",
             "company_ids": company_ids}
        )
        account_payable = Account.create(
            {"name": "Payable VCR", "code": "991004", "account_type": "liability_payable",
             "reconcile": True, "company_ids": company_ids}
        )
        account_receivable = Account.create(
            {"name": "Receivable VCR", "code": "991001", "account_type": "asset_receivable",
             "reconcile": True, "company_ids": company_ids}
        )
        Partner = cls.env["res.partner"]
        partner_vals = {
            "property_account_payable_id": account_payable.id,
            "property_account_receivable_id": account_receivable.id,
        }
        cls.vendor_a = Partner.create({"name": "Proveedor A", **partner_vals})
        cls.vendor_b = Partner.create({"name": "Proveedor B", **partner_vals})
        tax = cls.env["account.tax"].create(
            {"name": "IVA 16% VCR", "amount": 16, "amount_type": "percent",
             "type_tax_use": "purchase", "company_id": cls.company.id}
        )
        account_income = Account.create(
            {"name": "Income VCR", "code": "991002", "account_type": "income",
             "company_ids": company_ids}
        )
        sale_tax = cls.env["account.tax"].create(
            {"name": "IVA 16% Venta VCR", "amount": 16, "amount_type": "percent",
             "type_tax_use": "sale", "company_id": cls.company.id}
        )
        cls.sale_journal = cls.env["account.journal"].create(
            {"name": "Ventas VCR", "type": "sale", "code": "VCRS",
             "company_id": cls.company.id, "default_account_id": account_income.id}
        )
        cls.sale_product = cls.env["product.product"].create(
            {"name": "Servicio venta VCR", "type": "service", "list_price": 100,
             "property_account_income_id": account_income.id,
             "taxes_id": [(6, 0, [sale_tax.id])]}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Producto VCR", "type": "service", "list_price": 100,
             "property_account_expense_id": cls.account_expense.id,
             "supplier_taxes_id": [(6, 0, [tax.id])]}
        )
        cls.journal = cls.env["account.journal"].create(
            {"name": "Compras VCR", "type": "purchase", "code": "VCRJ",
             "company_id": cls.company.id, "default_account_id": cls.account_expense.id}
        )

    def _bill(self, partner, number, correlative, post=False, move_type="in_invoice"):
        ctx = self.env["account.move"].with_context(
            default_move_type=move_type, default_journal_id=self.journal.id
        )
        with Form(ctx) as form:
            form.partner_id = partner
            form.name = number
            if correlative:
                form.correlative = correlative
            form.invoice_date = fields.Date.today()
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = 100
        move = form.save()
        if post:
            move.action_post()
            # The database indexes only fire on flush: without it a clash with
            # the core unique name index would go unnoticed in the test.
            self.env.flush_all()
        return move

    # R1
    def test_same_control_with_another_bill_number_is_allowed(self):
        self._bill(self.vendor_a, "0001", "00001", post=True)
        second = self._bill(self.vendor_a, "0002", "00001", post=True)
        self.assertEqual(second.state, "posted")

    # R2
    def test_exact_duplicate_is_blocked_naming_the_existing_bill(self):
        first = self._bill(self.vendor_a, "0001", "00001", post=True)
        with self.assertRaises(ValidationError) as caught:
            self._bill(self.vendor_a, "0001", "00001", post=True)
        self.assertIn(first.name, str(caught.exception))
        self.assertIn("00001", str(caught.exception))

    # R3
    def test_other_vendor_does_not_clash(self):
        """Same invoice number and control for another vendor, in the same
        journal: the core unique name index used to block it."""
        first = self._bill(self.vendor_a, "0001", "00001", post=True)
        other = self._bill(self.vendor_b, "0001", "00001", post=True)
        self.assertEqual((first.name, other.name), ("0001", "0001"))
        self.assertEqual(other.state, "posted")

    # R4
    def test_drafts_with_same_data_are_blocked_when_confirmed(self):
        first = self._bill(self.vendor_a, "0001", "PRB9901")
        second = self._bill(self.vendor_a, "0001", "PRB9901")
        self.assertEqual((first.state, second.state), ("draft", "draft"))
        first.action_post()
        with self.assertRaises(ValidationError) as caught:
            second.action_post()
        self.assertIn(first.name, str(caught.exception))
        self.assertEqual(second.state, "draft")

    def test_control_typed_after_creation_is_validated_on_confirm(self):
        """Bills created without control and edited later: no posted twin
        exists while typing, so the save passes; the confirmation of the
        second one must still catch the duplicate."""
        first = self._bill(self.vendor_a, "0001", False)
        second = self._bill(self.vendor_a, "0001", False)
        for bill in (first, second):
            with Form(bill) as form:
                form.correlative = "00001"
        first.action_post()
        with self.assertRaises(ValidationError) as caught:
            second.action_post()
        self.assertIn(first.name, str(caught.exception))

    def test_typing_a_duplicate_against_a_posted_bill_is_blocked_on_save(self):
        first = self._bill(self.vendor_a, "0001", "00001", post=True)
        second = self._bill(self.vendor_a, "0001", False)
        with self.assertRaises(ValidationError) as caught:
            with Form(second) as form:
                form.correlative = "00001"
        self.assertIn(first.name, str(caught.exception))

    def test_editing_the_bill_number_into_a_duplicate_is_blocked_on_save(self):
        """Same control with another bill number is valid; typing the bill
        number of the posted twin afterwards in the form makes it an exact
        duplicate and the save must be rejected."""
        first = self._bill(self.vendor_a, "0001", "00001", post=True)
        second = self._bill(self.vendor_a, "0002", "00001")
        with self.assertRaises(ValidationError) as caught:
            with Form(second) as form:
                form.name = "0001"
        self.assertIn(first.name, str(caught.exception))

    def test_editing_the_bill_number_to_a_different_one_is_allowed(self):
        self._bill(self.vendor_a, "0001", "00001", post=True)
        second = self._bill(self.vendor_a, "0001", False)
        with Form(second) as form:
            form.correlative = "00002"
            form.name = "0003"
        second.action_post()
        self.assertEqual(second.state, "posted")

    def test_duplicates_confirmed_together_are_blocked(self):
        first = self._bill(self.vendor_a, "0001", "00001")
        second = self._bill(self.vendor_a, "0001", "00001")
        with self.assertRaises(ValidationError):
            (first | second).action_post()

    # R5
    def test_cancelled_bills_do_not_count(self):
        first = self._bill(self.vendor_a, "0001", "00001", post=True)
        first.button_cancel()
        self.assertEqual(first.state, "cancel")
        new = self._bill(self.vendor_a, "0001", "00001", post=True)
        self.assertEqual(new.state, "posted")

    def test_cancelling_a_posted_bill_is_not_blocked(self):
        first = self._bill(self.vendor_a, "0001", "00001", post=True)
        first.button_cancel()
        self.assertEqual(first.state, "cancel")

    # Scope
    def test_credit_notes_follow_the_same_rule(self):
        self._bill(self.vendor_a, "0001", "00001", post=True, move_type="in_refund")
        ok = self._bill(self.vendor_a, "0002", "00001", post=True, move_type="in_refund")
        self.assertEqual(ok.state, "posted")
        with self.assertRaises(ValidationError):
            self._bill(self.vendor_a, "0001", "00001", post=True, move_type="in_refund")

    # Criterion 3: sales keep blocking a repeated control number
    def _sale_invoice(self, partner, correlative, post=True):
        # The control number of a sale is assigned at confirmation and is not
        # editable in the form, so the documents are created with it, as the
        # existing correlative tests do.
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": fields.Date.today(),
                "correlative": correlative,
                "invoice_line_ids": [
                    (0, 0, {"product_id": self.sale_product.id, "quantity": 1,
                            "price_unit": 100})
                ],
            }
        )
        if post:
            # Without this context l10n_ve_accountant returns an alert wizard
            # instead of posting the sale.
            self.post_sale(move)
        return move

    def post_sale(self, move):
        move.with_context(move_action_post_alert=True).action_post()

    def test_sales_still_block_a_repeated_control_number(self):
        first = self._sale_invoice(self.vendor_a, "00077")
        self.assertEqual(first.state, "posted")
        with self.assertRaises(ValidationError) as caught:
            self._sale_invoice(self.vendor_a, "00077")
        self.assertIn(first.name, str(caught.exception))

    def test_sales_block_the_repeated_control_number_for_any_customer(self):
        """Sales are unique per company, not per customer, and the vendor
        bill number does not matter."""
        self._sale_invoice(self.vendor_a, "00078")
        with self.assertRaises(ValidationError):
            self._sale_invoice(self.vendor_b, "00078")
