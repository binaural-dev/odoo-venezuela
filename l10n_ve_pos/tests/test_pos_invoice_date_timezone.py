"""A POS order invoiced late in the Venezuelan evening lands its invoice on
the wrong calendar day. ``point_of_sale/models/pos_order.py::
_prepare_invoice_vals`` converts ``date_order`` (UTC) to
``self.env.user.tz``, falling back to **UTC** when no timezone is
configured -- common for a POS/cashier account. In Venezuela (UTC-4), from
the evening onward the UTC calendar day is already "tomorrow", so the
invoice (and the ``l10n_ve_rate`` lookup that depends on its date) lands
one day ahead of the real Venezuelan day.

``date_order`` below is 2026-10-28 02:00 UTC, still 2026-10-27 22:00 in
America/Caracas -- the exact window reported against production.
"""

from datetime import datetime

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosInvoiceDateTimezone(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create({
            "name": "Test VE POS TZ Co",
            "currency_id": usd.id,
            "country_id": cls.env.ref("base.ve").id,
        })
        vef = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VEF")], limit=1)
        )
        if vef and not vef.active:
            vef.active = True
        cls.foreign_currency = vef
        cls.company.write({"foreign_currency_id": cls.foreign_currency.id})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        # Reproduces the trigger: a cashier/session user with no tz
        # configured, which is exactly when core's _prepare_invoice_vals
        # falls back to UTC instead of the Venezuelan calendar day.
        cls.env.user.tz = False

        Account = cls.env["account.account"]
        cls.account_receivable = Account.create({
            "name": "TZ Receivable",
            "code": "1200TZ",
            "account_type": "asset_receivable",
            "company_ids": [(6, 0, [cls.company.id])],
            "reconcile": True,
        })
        cls.company.write({"account_default_pos_receivable_account_id": cls.account_receivable.id})
        cls.account_income = Account.create({
            "name": "TZ Income",
            "code": "4000TZ",
            "account_type": "income",
            "company_ids": [(6, 0, [cls.company.id])],
        })
        cls.account_bank = Account.create({
            "name": "TZ Bank",
            "code": "1000TZ",
            "account_type": "asset_cash",
            "company_ids": [(6, 0, [cls.company.id])],
        })
        cls.company.partner_id.with_company(cls.company).write({
            "property_account_receivable_id": cls.account_receivable.id,
            "property_account_payable_id": cls.account_receivable.id,
        })
        # Invoicing a POS order reconciles its payment against the invoice,
        # which l10n_ve_accountant routes through its own alternate-currency
        # exchange difference handling -- unrelated to the timezone fix
        # under test, but required for the reconciliation itself to go
        # through at all.
        cls.account_exchange_gain = Account.create({
            "name": "TZ Exchange Gain",
            "code": "7700TZ",
            "account_type": "income_other",
            "company_ids": [(6, 0, [cls.company.id])],
        })
        cls.account_exchange_loss = Account.create({
            "name": "TZ Exchange Loss",
            "code": "8700TZ",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company.id])],
        })
        cls.exchange_journal = cls.env["account.journal"].create({
            "name": "TZ Exchange Difference",
            "type": "general",
            "code": "TZEXCH",
            "company_id": cls.company.id,
        })
        cls.company.write({
            "currency_exchange_journal_id": cls.exchange_journal.id,
            "income_currency_exchange_account_id": cls.account_exchange_gain.id,
            "expense_currency_exchange_account_id": cls.account_exchange_loss.id,
        })

        cls.tax_group = cls.env["account.tax.group"].create(
            {"name": "TZ Tax Group", "company_id": cls.company.id}
        )
        cls.tax = cls.env["account.tax"].create({
            "name": "TZ Tax 16%",
            "amount": 16.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "tax_group_id": cls.tax_group.id,
            "company_id": cls.company.id,
        })
        cls.company.write({"account_purchase_tax_id": cls.tax.id})
        cls.product_category = cls.env["product.category"].create({
            "name": "TZ Category",
            "property_account_income_categ_id": cls.account_income.id,
            "property_account_expense_categ_id": cls.account_income.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "TZ Product",
            "type": "service",
            "lst_price": 100.0,
            "available_in_pos": True,
            "company_id": cls.company.id,
            "categ_id": cls.product_category.id,
            "taxes_id": [(6, 0, cls.tax.ids)],
        })
        cls.product.with_company(cls.company).write({"property_account_income_id": cls.account_income.id})

        manual_in = cls.env.ref("account.account_payment_method_manual_in")
        manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.bank_journal = cls.env["account.journal"].create({
            "name": "TZ Bank Journal",
            "type": "bank",
            "code": "TZBJ",
            "company_id": cls.company.id,
            "default_account_id": cls.account_bank.id,
            "inbound_payment_method_line_ids": [
                (0, 0, {"payment_method_id": manual_in.id, "payment_account_id": cls.account_bank.id})
            ],
            "outbound_payment_method_line_ids": [
                (0, 0, {"payment_method_id": manual_out.id, "payment_account_id": cls.account_bank.id})
            ],
        })
        cls.payment_method = cls.env["pos.payment.method"].create({
            "name": "TZ Card",
            "is_cash_count": False,
            "company_id": cls.company.id,
            "journal_id": cls.bank_journal.id,
            "outstanding_account_id": cls.account_bank.id,
        })
        cls.sale_journal = cls.env["account.journal"].create({
            "name": "TZ Sale Journal",
            "type": "sale",
            "code": "TZSJ",
            "company_id": cls.company.id,
        })
        cls.invoice_journal = cls.env["account.journal"].create({
            "name": "TZ Invoice Journal",
            "type": "sale",
            "code": "TZIJ",
            "company_id": cls.company.id,
        })
        cls.config = cls.env["pos.config"].create({
            "name": "TZ Config",
            "company_id": cls.company.id,
            "journal_id": cls.sale_journal.id,
            "invoice_journal_id": cls.invoice_journal.id,
            "payment_method_ids": [(6, 0, [cls.payment_method.id])],
        })
        cls.session = cls.env["pos.session"].create({
            "config_id": cls.config.id,
            "user_id": cls.env.user.id,
        })

    def _create_and_invoice_order(self, date_order):
        order = self.env["pos.order"].create({
            "company_id": self.company.id,
            "session_id": self.session.id,
            "partner_id": self.company.partner_id.id,
            "pricelist_id": self.company.partner_id.property_product_pricelist.id,
            "date_order": date_order,
            "amount_total": 116.0,
            "amount_tax": 16.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "last_order_preparation_change": "{}",
            "lines": [Command.create({
                "name": "OL/TZ/0001",
                "product_id": self.product.id,
                "price_unit": 100.0,
                "discount": 0.0,
                "qty": 1.0,
                "price_subtotal": 100.0,
                "price_subtotal_incl": 116.0,
                "tax_ids": [Command.set(self.tax.ids)],
            })],
        })
        order.add_payment({
            "name": "OL/TZ/0001/P",
            "pos_order_id": order.id,
            "amount": order.amount_total,
            "payment_method_id": self.payment_method.id,
            "payment_date": order.date_order,
        })
        order.write({"state": "paid"})
        order.action_pos_order_invoice()
        return order

    def test_invoice_date_uses_venezuela_day_not_utc_day(self):
        """A rate exists only for 2026-10-27 (Venezuela's actual day).
        Invoicing the order must land on it instead of 10-28 (UTC)."""
        self.env["res.currency.rate"].create({
            "currency_id": self.foreign_currency.id,
            "company_id": self.company.id,
            "name": "2026-10-27",
            "company_rate": 380.0,
        })

        order = self._create_and_invoice_order(datetime(2026, 10, 28, 2, 0, 0))

        self.assertEqual(
            order.account_move.invoice_date,
            fields.Date.from_string("2026-10-27"),
        )
