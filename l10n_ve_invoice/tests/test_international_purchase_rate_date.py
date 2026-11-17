from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestInternationalPurchaseRateDate(TransactionCase):
    """In an international purchase (import) journal the rate date may be later
    than the invoice date: only the rate existence on both dates is validated."""

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef.active = True
        self.currency_usd.active = True
        self.company.write(
            {
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
            }
        )
        today = fields.Date.context_today(self.env["account.move"])
        self.invoice_day = today - timedelta(days=30)
        self.rate_day = today - timedelta(days=10)
        for day in (self.invoice_day, self.rate_day, today):
            self._set_usd_rate(day, 40.0)

        self.partner = self.env["res.partner"].create({"name": "Proveedor Importacion"})
        account = self.env["account.account"].create(
            {
                "name": "Gasto Importacion",
                "code": "681777",
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.tax = self.env["account.tax"].create(
            {
                "name": "IVA 16% Importacion",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
            }
        )
        self.product = self.env["product.product"].create(
            {"name": "Producto Importado", "type": "service"}
        )
        self.journal_import = self._journal("IMPJ", account, international=True)
        self.journal_local = self._journal("LOCJ", account, international=False)

    def _journal(self, code, account, international):
        return self.env["account.journal"].create(
            {
                "name": "Compras %s" % code,
                "type": "purchase",
                "code": code,
                "company_id": self.company.id,
                "default_account_id": account.id,
                "is_purchase_international": international,
            }
        )

    def _set_usd_rate(self, day, rate):
        Rate = self.env["res.currency.rate"]
        for currency, inverse in ((self.currency_vef, 1.0), (self.currency_usd, rate)):
            vals = {"inverse_company_rate": inverse}
            existing = Rate.search(
                [
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", self.company.id),
                    ("name", "=", day),
                ]
            )
            if existing:
                existing.write(vals)
            else:
                Rate.create(
                    dict(vals, name=day, currency_id=currency.id, company_id=self.company.id)
                )

    def _bill(self, journal, rate_date, invoice_date=None, accounting_date=None):
        invoice_date = invoice_date or self.invoice_day
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": journal.id,
                "invoice_date": rate_date,
                "invoice_date_display": invoice_date,
                "date": accounting_date or rate_date,
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

    def test_import_rate_date_later_than_invoice_date_posts(self):
        bill = self._bill(self.journal_import, self.rate_day)
        bill.action_post()
        self.assertEqual(bill.state, "posted")

    def test_local_purchase_rate_date_later_than_invoice_date_is_blocked(self):
        bill = self._bill(self.journal_local, self.rate_day)
        with self.assertRaisesRegex(ValidationError, "cannot be later than"):
            bill.action_post()

    def test_import_without_rate_on_rate_date_is_blocked(self):
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.currency_usd.id), ("name", "=", self.rate_day)]
        ).unlink()
        with self.assertRaises(UserError):
            self._bill(self.journal_import, self.rate_day).action_post()

    def test_import_without_rate_on_invoice_date_is_blocked(self):
        bill = self._bill(self.journal_import, self.rate_day)
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.currency_usd.id), ("name", "=", self.invoice_day)]
        ).unlink()
        with self.assertRaises(UserError):
            bill.action_post()
