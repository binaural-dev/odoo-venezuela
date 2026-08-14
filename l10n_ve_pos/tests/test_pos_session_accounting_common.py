"""Shared test scaffolding for Slice C1 (accumulators) and Slice C2 (move
creation) of the l10n_ve_pos Odoo 17 → Odoo 19 migration.

Both slices share the same VES-as-foreign environment, payment methods, and
chart of accounts setup. The class extracted here is intentionally lean: it
builds ONE VEF foreign-currency company, ONE POS config with TWO cash methods
(slotted C1) and TWO bank methods (slotted C2), so each slice only needs to
add its own scenarios on top.

Spec: ``openspec/changes/l10n-ve-pos-migration-plan/specs/pos-odoo19-session-accounting/spec.md``
Doc:   ``.../specs/pos-odoo19-session-accounting/key-map.md``
"""

from odoo import Command
from odoo.tests import TransactionCase


class TestPosSessionAccountingBase(TransactionCase):
    """Lean Odoo 19 environment shared by Slice C1 + C2 test classes.

    Public attributes (set up once in ``setUpClass``):

    - ``company``               — VEF foreign-currency company (currency=USD)
    - ``foreign_currency``      — VEF (used as the "foreign" currency)
    - ``account_receivable``    — generic asset_receivable (C1/C2 cash)
    - ``account_income``        — generic income account
    - ``account_cash``          — generic asset_cash (cash journal default)
    - ``account_bank``          — generic asset_cash (bank journal default)
    - ``account_pos_receivable``— POS-default receivable (bank journal uses this)
    - ``cash_journal``          — combined cash journal (VEF)
    - ``split_cash_journal``    — split cash journal (VEF)
    - ``bank_journal``          — bank journal (VEF, with inbound payment method line)
    - ``invoice_journal``       — sale/invoice journal (VEF)
    - ``sale_journal``          — sale journal (VEF)
    - ``combined_cash_method``  — pos.payment.method cash, no split (combine bucket)
    - ``split_cash_method``     — pos.payment.method cash, split_transactions=True (split bucket)
    - ``combined_bank_method``  — pos.payment.method bank, no split (combine bucket)
    - ``split_bank_method``     — pos.payment.method bank, split_transactions=True (split bucket)
    - ``tax`` / ``tax_group``   — single sale tax for order lines
    - ``product_category``      — category for the test product
    - ``product``               — single test product
    - ``config``                — POS config (foreign-currency, all four methods)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Slice C Co",
                "currency_id": usd.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )


        vef = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VEF")], limit=1)
        )
        if vef and not vef.active:
            vef.active = True
        cls.foreign_currency = vef
        cls.company.write({"foreign_currency_id": cls.foreign_currency.id})

        Account = cls.env["account.account"]
        cls.account_receivable = Account.create(
            {
                "name": "C Receivable",
                "code": "120000C",
                "account_type": "asset_receivable",
                "company_ids": [(6, 0, [cls.company.id])],
                "reconcile": True,
            }
        )
        cls.account_pos_receivable = Account.create(
            {
                "name": "C POS Receivable",
                "code": "120001C",
                "account_type": "asset_receivable",
                "company_ids": [(6, 0, [cls.company.id])],
                "reconcile": True,
            }
        )
        cls.company.write(
            {"account_default_pos_receivable_account_id": cls.account_pos_receivable.id}
        )
        cls.account_income = Account.create(
            {
                "name": "C Income",
                "code": "400000C",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        # The company's partner must point at the test receivable account,
        # otherwise ``_find_accounting_partner(company.partner_id)`` returns
        # an account that doesn't belong to the test company and the
        # Odoo 19 ``_check_company`` on ``account.move.line.create`` raises
        # ``UserError`` in C2 tests.
        # ``property_account_receivable_id`` is a company-dependent field:
        # the write MUST happen under the test company context so the value
        # is stored for that company's scope.
        cls.company.partner_id.with_company(cls.company).write(
            {
                "property_account_receivable_id": cls.account_receivable.id,
                "property_account_payable_id": cls.account_receivable.id,
            }
        )
        cls.account_cash = Account.create(
            {
                "name": "C Cash",
                "code": "100000C",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.account_bank = Account.create(
            {
                "name": "C Bank",
                "code": "110000C",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

        # --- Cash journals (C1 accumulators) ---
        cls.cash_journal = cls.env["account.journal"].create(
            {
                "name": "C Cash Journal",
                "type": "cash",
                "code": "CSC",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_cash.id,
            }
        )
        cls.split_cash_journal = cls.env["account.journal"].create(
            {
                "name": "C Split Cash Journal",
                "type": "cash",
                "code": "SCC",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_cash.id,
            }
        )
        cls.combined_cash_method = cls.env["pos.payment.method"].create(
            {
                "name": "C Combined Cash",
                "is_cash_count": True,
                "split_transactions": False,
                "company_id": cls.company.id,
                "journal_id": cls.cash_journal.id,
            }
        )
        cls.combined_cash_method.write({"is_foreign_currency": True})
        cls.split_cash_method = cls.env["pos.payment.method"].create(
            {
                "name": "C Split Cash",
                "is_cash_count": True,
                "split_transactions": True,
                "company_id": cls.company.id,
                "journal_id": cls.split_cash_journal.id,
            }
        )
        cls.split_cash_method.write({"is_foreign_currency": True})

        # --- Bank journal (C2 split + combine) ---
        # A bank journal in Odoo 19 must have BOTH inbound and outbound
        # payment method lines with ``payment_account_id`` set — the
        # ``l10n_ve_accountant`` constraint
        # (``_check_payment_method_line_accounts``) raises otherwise.
        manual_in = cls.env.ref("account.account_payment_method_manual_in")
        manual_out = cls.env.ref("account.account_payment_method_manual_out")
        cls.bank_journal = cls.env["account.journal"].create(
            {
                "name": "C Bank Journal",
                "type": "bank",
                "code": "BJC",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "default_account_id": cls.account_bank.id,
                "inbound_payment_method_line_ids": [
                    (
                        0,
                        0,
                        {
                            "payment_method_id": manual_in.id,
                            "payment_account_id": cls.account_bank.id,
                        },
                    )
                ],
                "outbound_payment_method_line_ids": [
                    (
                        0,
                        0,
                        {
                            "payment_method_id": manual_out.id,
                            "payment_account_id": cls.account_bank.id,
                        },
                    )
                ],
            }
        )
        cls.combined_bank_method = cls.env["pos.payment.method"].create(
            {
                "name": "C Combined Bank",
                "is_cash_count": False,
                "split_transactions": False,
                "company_id": cls.company.id,
                "journal_id": cls.bank_journal.id,
                "outstanding_account_id": cls.account_bank.id,
            }
        )
        cls.combined_bank_method.write({"is_foreign_currency": True})
        cls.split_bank_method = cls.env["pos.payment.method"].create(
            {
                "name": "C Split Bank",
                "is_cash_count": False,
                "split_transactions": True,
                "company_id": cls.company.id,
                "journal_id": cls.bank_journal.id,
                "outstanding_account_id": cls.account_bank.id,
            }
        )
        cls.split_bank_method.write({"is_foreign_currency": True})

        # --- Tax + product (needed for any order) ---
        cls.tax_group = cls.env["account.tax.group"].create(
            {"name": "C Tax Group", "company_id": cls.company.id}
        )
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "C Tax",
                "amount": 16.0,
                "type_tax_use": "sale",
                "tax_group_id": cls.tax_group.id,
                "company_id": cls.company.id,
            }
        )
        cls.product_category = cls.env["product.category"].create(
            {
                "name": "C Category",
                "property_account_income_categ_id": cls.account_income.id,
                "property_account_expense_categ_id": cls.account_income.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "C Product",
                "lst_price": 100.0,
                "standard_price": 50.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": cls.product_category.id,
                "taxes_id": [(6, 0, cls.tax.ids)],
            }
        )
        cls.product.with_company(cls.company).write(
            {"property_account_income_id": cls.account_income.id}
        )

        # --- POS sale + invoice journals + config ---
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "C Sale Journal",
                "type": "sale",
                "code": "SJC",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.invoice_journal = cls.env["account.journal"].create(
            {
                "name": "C Invoice Journal",
                "type": "sale",
                "code": "IJC",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "C Config",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "journal_id": cls.sale_journal.id,
                "invoice_journal_id": cls.invoice_journal.id,
                "payment_method_ids": [
                    (
                        6,
                        0,
                        [
                            cls.combined_cash_method.id,
                            cls.split_cash_method.id,
                            cls.combined_bank_method.id,
                            cls.split_bank_method.id,
                        ],
                    )
                ],
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _create_paid_order(
        cls,
        session,
        *,
        method,
        amount=116.0,
        tax_amount=16.0,
        foreign_rate=36.5,
        invoiced=False,
        name="OL/C",
        partner_id=None,
    ):
        """Create a single paid order with one line and one payment.

        ``method`` is a ``pos.payment.method`` (combined cash, split cash,
        combined bank, split bank). The order is flipped to ``paid`` so
        ``_get_closed_orders()`` picks it up.

        ``partner_id`` defaults to the company's partner (the C2
        move-creation chain calls ``_find_accounting_partner`` on the
        payment's partner; without a partner the C2 chain raises
        ``AttributeError``). C1 tests ignore the partner (accumulators
        don't read it), so defaulting to the company partner is safe
        for both slices.
        """
        if partner_id is None:
            partner_id = cls.company.partner_id.id
        order = cls.env["pos.order"].create(
            {
                "company_id": cls.company.id,
                "session_id": session.id,
                "partner_id": partner_id,
                "pricelist_id": cls.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": amount,
                "foreign_currency_rate": foreign_rate,
                "lines": [
                    Command.create(
                        {
                            "name": name,
                            "product_id": cls.product.id,
                            "price_unit": amount - tax_amount,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": amount - tax_amount,
                            "price_subtotal_incl": amount,
                            "tax_ids": [(6, 0, cls.tax.ids)],
                            "foreign_price": (amount - tax_amount) * foreign_rate,
                        }
                    )
                ],
                "amount_total": amount,
                "amount_tax": tax_amount,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        order.add_payment(
            {
                "name": f"{name}/P",
                "pos_order_id": order.id,
                "amount": amount,
                "payment_method_id": method.id,
                "payment_date": order.date_order,
                "foreign_rate": foreign_rate,
                "foreign_amount": amount * foreign_rate,
            }
        )
        if invoiced:
            # Draft invoice (must not be posted) to flip ``is_invoiced`` without
            # tripping ``pos.payment._check_amount`` (which blocks edits on
            # posted orders).
            invoice = cls.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "journal_id": cls.invoice_journal.id,
                    "partner_id": cls.company.partner_id.id,
                }
            )
            order.write({"account_move": invoice.id})
        order.write({"state": "paid"})
        return order
