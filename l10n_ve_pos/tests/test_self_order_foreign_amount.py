"""Tests for the Kiosk/Self-Order foreign-currency creation contract.

Spec: ``openspec/changes/l10n-ve-pos-self-order-foreign-amount-fix/specs/
pos-self-order-foreign-amount/spec.md``

``foreign_amount_total`` is ``required=True`` on ``pos.order`` but is only
ever populated by a JS patch scoped to the cashier app's asset bundle
(``point_of_sale._assets_pos``). The native Kiosk/Self-Order app
(``pos_self_order``) loads a different bundle that never includes it, so
without a server-side fallback the INSERT raises a raw NOT NULL violation.
These tests exercise the fallback directly on ``pos.order.create`` — they
do NOT require ``pos_self_order`` to be installed, since
``_complete_values_from_session`` (the hook used) is pure core
``point_of_sale``.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos", "self_order_foreign_amount")
class TestSelfOrderForeignAmount(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Self Order Co",
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

        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Self Order Sale Journal",
                "type": "sale",
                "code": "SOJ",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Self Order Config",
                "company_id": cls.company.id,
                "currency_id": cls.foreign_currency.id,
                "journal_id": cls.sale_journal.id,
            }
        )

    def _create_session(self):
        return self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    def _base_order_vals(self, session):
        return {
            "company_id": self.company.id,
            "session_id": session.id,
            "partner_id": False,
            "pricelist_id": self.company.partner_id.property_product_pricelist.id,
            "amount_total": 100.0,
            "amount_tax": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "last_order_preparation_change": "{}",
        }

    def test_missing_foreign_amount_total_is_computed_via_convert(self):
        """Scenario: Pedido creado desde el Kiosko/Autopedido — el payload
        no trae foreign_amount_total/foreign_currency_rate y el servidor
        los debe completar con pos.config._convert/_get_pos_conversion_rate
        en vez de dejar NULL."""
        session = self._create_session()
        order = self.env["pos.order"].create(self._base_order_vals(session))

        expected_total = self.config._convert(
            100.0, self.config.currency_id, self.config.foreign_currency_id
        )
        expected_rate = self.config._get_pos_conversion_rate(
            self.config.currency_id, self.config.foreign_currency_id
        )
        self.assertNotEqual(expected_total, 0.0, "test setup must have a real rate")
        self.assertEqual(order.foreign_amount_total, expected_total)
        self.assertEqual(order.foreign_currency_rate, expected_rate)

    def test_explicit_foreign_amount_total_is_not_overwritten(self):
        """Scenario: Pedido creado desde la caja normal — el payload SÍ
        trae los valores (calculados por el patch JS), setdefault no debe
        pisarlos."""
        session = self._create_session()
        vals = self._base_order_vals(session)
        vals.update({"foreign_amount_total": 4234.0, "foreign_currency_rate": 36.5})
        order = self.env["pos.order"].create(vals)

        self.assertEqual(order.foreign_amount_total, 4234.0)
        self.assertEqual(order.foreign_currency_rate, 36.5)

    def test_company_without_foreign_currency_defaults_to_zero(self):
        """Scenario: Compañía sin moneda foránea configurada — no debe
        lanzar error, foreign_amount_total/foreign_currency_rate quedan en
        0.0 (mismo contrato que pos.config._convert/_get_pos_conversion_rate
        para "no hay conversión posible")."""
        no_foreign_company = self.env["res.company"].create(
            {
                "name": "Test VE No Foreign Co",
                "currency_id": self.env.ref("base.USD").id,
            }
        )
        journal = self.env["account.journal"].create(
            {
                "name": "No Foreign Sale Journal",
                "type": "sale",
                "code": "NFSJ",
                "company_id": no_foreign_company.id,
            }
        )
        config = self.env["pos.config"].create(
            {
                "name": "No Foreign Config",
                "company_id": no_foreign_company.id,
                "journal_id": journal.id,
            }
        )
        session = self.env["pos.session"].create(
            {"config_id": config.id, "user_id": self.env.ref("base.user_admin").id}
        )
        order = self.env["pos.order"].create(
            {
                "company_id": no_foreign_company.id,
                "session_id": session.id,
                "partner_id": False,
                "pricelist_id": (
                    no_foreign_company.partner_id.property_product_pricelist.id
                ),
                "amount_total": 100.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        self.assertEqual(order.foreign_amount_total, 0.0)
        self.assertEqual(order.foreign_currency_rate, 0.0)
