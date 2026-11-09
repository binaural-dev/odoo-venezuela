from odoo import fields
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_price_unit")
class TestInvoicePriceUnitPricelist(TransactionCase):
    """account_invoice_pricelist recomputes the line unit price from the
    pricelist every time the quantity changes. Without protection, a price typed
    by hand or inherited from another document (reversed invoice, sale order,
    synchronization) went back to the pricelist one: a credit note of an invoice
    at 25 dropped to 16 when the quantity went from 12 to 2 (task 84438).
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
            }
        )
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": self.currency_usd.id,
                "inverse_company_rate": 40.0,
                "company_id": self.company.id,
            }
        )

        self.account_receivable = self._get_or_create_account(
            "120000", "Receivable", "asset_receivable", reconcile=True
        )
        self.account_income = self._get_or_create_account("400000", "Income", "income")
        self.account_tax = self._get_or_create_account(
            "200000", "Tax Payable", "liability_current"
        )
        self.tax_16 = self.env["account.tax"].create(
            {
                "name": "VAT 16% price unit",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "invoice_repartition_line_ids": [
                    (0, 0, {"repartition_type": "base"}),
                    (0, 0, {"repartition_type": "tax", "account_id": self.account_tax.id}),
                ],
                "refund_repartition_line_ids": [
                    (0, 0, {"repartition_type": "base"}),
                    (0, 0, {"repartition_type": "tax", "account_id": self.account_tax.id}),
                ],
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Price unit product",
                "type": "consu",
                "list_price": 16.0,
                "property_account_income_id": self.account_income.id,
                "taxes_id": [(6, 0, self.tax_16.ids)],
            }
        )
        self.pricelist = self.env["product.pricelist"].create(
            {
                "name": "Price unit VEF pricelist",
                "currency_id": self.currency_vef.id,
                "company_id": self.company.id,
            }
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Price unit customer",
                "property_account_receivable_id": self.account_receivable.id,
                "property_product_pricelist": self.pricelist.id,
            }
        )
        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        )

    def _get_or_create_account(self, code, name, account_type, reconcile=False):
        account = self.env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", self.company.id)], limit=1
        )
        return account or self.env["account.account"].create(
            {
                "code": code,
                "name": name,
                "account_type": account_type,
                "company_ids": [(6, 0, self.company.ids)],
                "reconcile": reconcile,
            }
        )

    def _create_invoice(self, quantity, price_unit):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": quantity,
                            "price_unit": price_unit,
                        },
                    )
                ],
            }
        )

    def _new_invoice_form(self):
        move_form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        move_form.partner_id = self.partner
        move_form.invoice_date = fields.Date.today()
        return move_form

    def test_manual_price_survives_quantity_change(self):
        """A price typed by hand is kept when the quantity changes."""
        move_form = self._new_invoice_form()
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
            self.assertEqual(line_form.price_unit, 16.0)
            line_form.price_unit = 25.0
            line_form.quantity = 12
            self.assertEqual(line_form.price_unit, 25.0)
        invoice = move_form.save()

        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.quantity = 2
                self.assertEqual(line_form.price_unit, 25.0)
        self.assertEqual(invoice.invoice_line_ids.price_unit, 25.0)

    def test_reversal_keeps_origin_price(self):
        """The credit note keeps the invoice price when the quantity changes."""
        invoice = self._create_invoice(quantity=12, price_unit=25.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create(
            {
                "date": fields.Date.today(),
                "journal_id": invoice.journal_id.id,
                "reason": "Partial return",
            }
        )
        credit_note = self.env["account.move"].browse(wizard.refund_moves()["res_id"])
        self.assertEqual(credit_note.invoice_line_ids.price_unit, 25.0)

        with Form(credit_note) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.quantity = 2
                self.assertEqual(line_form.price_unit, 25.0)
        self.assertEqual(credit_note.invoice_line_ids.price_unit, 25.0)
        self.assertAlmostEqual(credit_note.amount_total, 58.0)

    def test_price_from_another_document_survives_quantity_write(self):
        """A price received on line creation is kept when the quantity is written."""
        invoice = self._create_invoice(quantity=12, price_unit=25.0)
        invoice.invoice_line_ids.quantity = 2
        self.assertEqual(invoice.invoice_line_ids.price_unit, 25.0)

    def test_pricelist_quantity_tiers_still_apply(self):
        """A price that came from the pricelist is still recomputed by quantity."""
        self.env["product.pricelist.item"].create(
            {
                "pricelist_id": self.pricelist.id,
                "applied_on": "0_product_variant",
                "product_id": self.product.id,
                "min_quantity": 10,
                "compute_price": "fixed",
                "fixed_price": 14.0,
            }
        )
        move_form = self._new_invoice_form()
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
            self.assertEqual(line_form.price_unit, 16.0)
            line_form.quantity = 10
            self.assertEqual(line_form.price_unit, 14.0)
            line_form.quantity = 2
            self.assertEqual(line_form.price_unit, 16.0)
        invoice = move_form.save()

        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.quantity = 12
                self.assertEqual(line_form.price_unit, 14.0)
        self.assertEqual(invoice.invoice_line_ids.price_unit, 14.0)

    def test_update_prices_button_overrides_manual_price(self):
        """The 'Update prices' button applies the pricelist even to manual prices."""
        invoice = self._create_invoice(quantity=12, price_unit=25.0)
        invoice.button_update_prices_from_pricelist()
        self.assertEqual(invoice.invoice_line_ids.price_unit, 16.0)

        invoice.invoice_line_ids.quantity = 2
        self.assertEqual(invoice.invoice_line_ids.price_unit, 16.0)
