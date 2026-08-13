"""Tests for the ``recompute_prices()`` foreign-currency sync contract.

Spec: ``l10n_ve_pos/openspec/changes/l10n-ve-pos-self-order-foreign-amount-fix/
specs/pos-self-order-foreign-amount/spec.md``

``pos_self_order.recompute_prices()`` recalculates ``amount_total``
authoritatively against the real catalog after the Kiosk/Self-Order
controller creates or updates an order (defense against a tampered client
payload). It never touches the Venezuelan foreign-currency fields on its
own, so ``l10n_ve_pos``'s provisional value (computed in
``_complete_values_from_session`` from the client-submitted, possibly wrong,
total) goes stale the moment this recompute corrects the total. This module
patches ``recompute_prices()`` to keep ``foreign_amount_total``/
``foreign_currency_rate`` in sync — these tests live here (not in
``l10n_ve_pos``) because ``recompute_prices`` only exists once
``pos_self_order`` is installed.
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestRecomputePricesForeignAmount(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Self Order Recompute Co",
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
        cls.account_income = Account.create(
            {
                "name": "Self Order Recompute Income",
                "code": "400000SOR",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        cls.product_category = cls.env["product.category"].create(
            {
                "name": "Self Order Recompute Category",
                "property_account_income_categ_id": cls.account_income.id,
                "property_account_expense_categ_id": cls.account_income.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Self Order Recompute Product",
                "lst_price": 100.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": cls.product_category.id,
            }
        )

        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Self Order Recompute Sale Journal",
                "type": "sale",
                "code": "SORJ",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Self Order Recompute Config",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "journal_id": cls.sale_journal.id,
            }
        )
        cls.session = cls.env["pos.session"].create(
            {
                "config_id": cls.config.id,
                "user_id": cls.env.ref("base.user_admin").id,
            }
        )

    def test_recompute_prices_resyncs_foreign_amount_total(self):
        """Scenario: El total local cambia tras recompute_prices() — el
        pedido se crea con un amount_total provisional (distinto del real
        de las líneas, simulando un payload manipulado/desactualizado del
        Kiosko); recompute_prices() corrige amount_total contra el
        catálogo real y este override debe recalcular
        foreign_amount_total/foreign_currency_rate a partir del valor ya
        corregido, no del provisional."""
        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": self.session.id,
                "partner_id": False,
                "pricelist_id": (
                    self.company.partner_id.property_product_pricelist.id
                ),
                # Provisional/wrong total, as if sent (and trusted) by a
                # tampered Kiosk client payload.
                "amount_total": 1.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
                "lines": [
                    Command.create(
                        {
                            "name": "OL/SOR/0001",
                            "product_id": self.product.id,
                            "price_unit": 100.0,
                            "discount": 0.0,
                            "qty": 1.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 100.0,
                        }
                    )
                ],
            }
        )
        # The provisional foreign_amount_total from
        # _complete_values_from_session was computed off the wrong
        # amount_total (1.0), so it must NOT already match the post-recompute
        # expectation — otherwise this test wouldn't be exercising the fix.
        provisional_foreign_total = order.foreign_amount_total

        order.recompute_prices()

        self.assertEqual(
            order.amount_total,
            100.0,
            "recompute_prices() must correct amount_total from the real catalog price",
        )
        expected_foreign_total = self.config._convert(
            order.amount_total, order.currency_id, self.config.foreign_currency_id
        )
        self.assertNotEqual(
            provisional_foreign_total,
            expected_foreign_total,
            "test setup must start from a stale provisional value",
        )
        self.assertEqual(order.foreign_amount_total, expected_foreign_total)
        self.assertEqual(
            order.foreign_currency_rate,
            self.config._get_pos_conversion_rate(
                order.currency_id, self.config.foreign_currency_id
            ),
        )
