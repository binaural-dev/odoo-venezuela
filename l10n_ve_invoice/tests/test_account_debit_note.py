from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestAccountDebitNote(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company.currency_id = self.currency_vef
        self.company.foreign_currency_id = self.currency_usd

        self.partner = self.env["res.partner"].create({"name": "Test DN Partner"})

        self.account_revenue = self.env["account.account"].create(
            {
                "name": "Revenue DN",
                "code": "980001",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.journal_sale = self.env["account.journal"].create(
            {
                "name": "Sale DN Journal",
                "type": "sale",
                "code": "DNSJ",
                "company_id": self.company.id,
                "default_account_id": self.account_revenue.id,
            }
        )
        self.journal_debit = self.env["account.journal"].create(
            {
                "name": "Debit DN Journal",
                "type": "sale",
                "code": "DNDJ",
                "company_id": self.company.id,
                "is_debit": True,
                "default_account_id": self.account_revenue.id,
            }
        )

        self.tax = self.env["account.tax"].create(
            {
                "name": "IVA 16% DN",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product DN",
                "type": "service",
                "list_price": 100,
                "taxes_id": [(6, 0, [self.tax.id])],
            }
        )

    def _create_posted_invoice(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_sale.id,
                "invoice_date": fields.Date.today(),
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
                            "tax_ids": [(6, 0, [self.tax.id])],
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_filter_enabled_true(self):
        self.company.auto_select_debit_note_journal = True
        invoice = self._create_posted_invoice()
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=[invoice.id], active_id=invoice.id
        ).new(
            {
                "journal_type": "sale",
            }
        )
        self.assertTrue(wizard.filter_enabled)

    def test_filter_enabled_false(self):
        self.company.auto_select_debit_note_journal = False
        invoice = self._create_posted_invoice()
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=[invoice.id], active_id=invoice.id
        ).new(
            {
                "journal_type": "sale",
            }
        )
        self.assertFalse(wizard.filter_enabled)
