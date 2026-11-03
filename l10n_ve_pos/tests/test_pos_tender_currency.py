"""Métodos de pago en una tercera moneda (moneda de cobro, p. ej. EUR) — tarea 86066.

La caja está en la moneda de la compañía y la alterna es la de siempre; un
método con ``tender_currency_id`` se cobra en una tercera moneda: el motor de
conversión (``pos.config._get_pos_conversion_rate``) conoce su tasa del día,
cada pago guarda lo cobrado en esa moneda (``tender_amount``) y el cruce al
diario real en esa moneda lleva ese monto como ``amount_currency``.

En este fixture la compañía está en USD y la alterna es VEF (ver
``TestPosSessionAccountingBase``); la tercera moneda es EUR.
"""

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

# 1 EUR = 1,16 USD (company_rate EUR = 1 / 1,16).
USD_PER_EUR = 1.16


@tagged("post_install", "-at_install", "l10n_ve_pos", "tender_currency")
class TestPosTenderCurrency(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # compute_rate (l10n_ve_rate) busca las tasas de env.company.
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        cls._create_rate_of_day(40.0)
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.context_today(cls.env.user),
                "currency_id": cls.eur.id,
                "company_id": cls.company.id,
                "rate": 1 / USD_PER_EUR,
            }
        )
        Account = cls.env["account.account"]
        Journal = cls.env["account.journal"]

        def account(name, code, account_type="asset_current"):
            return Account.create(
                {
                    "name": name,
                    "code": code,
                    "account_type": account_type,
                    "company_ids": [(6, 0, [cls.company.id])],
                }
            )

        manual_in = cls.env.ref("account.account_payment_method_manual_in")
        manual_out = cls.env.ref("account.account_payment_method_manual_out")

        def bank_journal(name, code, account, currency=None, suspense=None):
            vals = {
                "name": name,
                "type": "bank",
                "code": code,
                "company_id": cls.company.id,
                "default_account_id": account.id,
                "inbound_payment_method_line_ids": [
                    (0, 0, {"payment_method_id": manual_in.id, "payment_account_id": account.id})
                ],
                "outbound_payment_method_line_ids": [
                    (0, 0, {"payment_method_id": manual_out.id, "payment_account_id": account.id})
                ],
            }
            if currency:
                vals["currency_id"] = currency.id
            if suspense:
                vals["suspense_account_id"] = suspense.id
            return Journal.create(vals)

        # Caja real en EUR (cross_journal) y diario del cruce.
        cls.account_eur_cash = account("T Caja EUR", "110086T", "asset_cash")
        cls.account_eur_suspense = account("T Transitoria Caja EUR", "190086T")
        cls.eur_journal = bank_journal(
            "T Caja EUR", "TEU86", cls.account_eur_cash, currency=cls.eur,
            suspense=cls.account_eur_suspense,
        )
        cls.cross_account_journal = Journal.create(
            {"name": "T Cruce EUR", "type": "general", "code": "TCE86", "company_id": cls.company.id}
        )

        # Caja en la moneda de la compañía (USD): diarios sin moneda.
        cls.account_transit = account("T Metodo EUR", "100087T", "asset_cash")
        cls.account_transit_suspense = account("T Transitoria metodo EUR", "190087T")
        base_cash_journal = Journal.create(
            {
                "name": "T Efectivo USD", "type": "cash", "code": "TEC86",
                "company_id": cls.company.id, "default_account_id": cls.account_cash.id,
            }
        )
        transit_journal = Journal.create(
            {
                "name": "T Efectivo EUR (transitorio)", "type": "cash", "code": "TET86",
                "company_id": cls.company.id, "default_account_id": cls.account_transit.id,
                "suspense_account_id": cls.account_transit_suspense.id,
            }
        )
        cls.account_transit_bank = account("T Banco EUR transitorio", "110088T", "asset_cash")
        transit_bank_journal = bank_journal("T Banco EUR (transitorio)", "TEB86", cls.account_transit_bank)
        Method = cls.env["pos.payment.method"]
        cls.base_cash_method = Method.create(
            {"name": "T Efectivo USD", "company_id": cls.company.id, "journal_id": base_cash_journal.id}
        )
        method_vals = {
            "company_id": cls.company.id,
            "tender_currency_id": cls.eur.id,
            "cross_journal": cls.eur_journal.id,
            "cross_account_journal": cls.cross_account_journal.id,
        }
        cls.eur_method = Method.create(
            dict(method_vals, name="T Efectivo EUR", journal_id=transit_journal.id)
        )
        cls.eur_bank_method = Method.create(
            dict(
                method_vals, name="T Zelle EUR", journal_id=transit_bank_journal.id,
                split_transactions=True, outstanding_account_id=cls.account_transit_bank.id,
            )
        )
        cls.usd_config = cls.env["pos.config"].create(
            {
                "name": "T Caja USD con EUR",
                "company_id": cls.company.id,
                "journal_id": Journal.create(
                    {"name": "T Ventas PdV", "type": "sale", "code": "TSJ86", "company_id": cls.company.id}
                ).id,
                "invoice_journal_id": Journal.create(
                    {"name": "T Facturas PdV", "type": "sale", "code": "TIJ86", "company_id": cls.company.id}
                ).id,
                "payment_method_ids": [
                    (6, 0, [cls.base_cash_method.id, cls.eur_method.id, cls.eur_bank_method.id])
                ],
            }
        )

    def _new_session(self):
        return self.env["pos.session"].create(
            {"config_id": self.usd_config.id, "user_id": self.env.ref("base.user_admin").id}
        )

    def _eur_order(self, session, amount, tender_amount, foreign_rate=36.5, name="OL/EUR"):
        order = self._create_paid_order(
            session, method=self.eur_method, amount=amount, tax_amount=0.0,
            foreign_rate=foreign_rate, name=name,
        )
        order.payment_ids.write({"tender_amount": tender_amount})
        order._set_payment_tender_values()
        return order

    def _cross_moves(self):
        return self.env["account.move"].search(
            [("journal_id", "=", self.cross_account_journal.id), ("company_id", "=", self.company.id)]
        )

    # ------------------------------------------------------------------
    # Motor de conversión
    # ------------------------------------------------------------------
    def test_config_exposes_the_rates_of_the_tender_currency(self):
        rates = self.usd_config.tender_currency_rates[str(self.eur.id)]
        self.assertAlmostEqual(rates["foreign_rate"], USD_PER_EUR, places=9)
        self.assertAlmostEqual(rates["foreign_inverse_rate"], 1 / USD_PER_EUR, places=9)

    def test_conversion_between_pos_currency_and_tender_currency(self):
        config = self.usd_config
        usd = config.currency_id
        self.assertAlmostEqual(config._get_pos_conversion_rate(self.eur, usd), USD_PER_EUR, places=9)
        self.assertAlmostEqual(config._get_pos_conversion_rate(usd, self.eur), 1 / USD_PER_EUR, places=9)
        self.assertEqual(config._convert(100.0, self.eur, usd), 116.0)
        self.assertEqual(config._convert(116.0, usd, self.eur), 100.0)

    def test_tender_to_foreign_goes_through_the_pos_currency_without_rounding_the_rate(self):
        config = self.usd_config
        expected = USD_PER_EUR * config.foreign_inverse_rate
        self.assertAlmostEqual(
            config._get_pos_conversion_rate(self.eur, self.foreign_currency), expected, places=12
        )
        self.assertEqual(
            config._convert(10.0, self.eur, self.foreign_currency),
            self.foreign_currency.round(10.0 * expected),
        )

    def test_main_foreign_pair_is_unchanged(self):
        config = self.usd_config
        usd = config.currency_id
        self.assertEqual(
            config._get_pos_conversion_rate(usd, self.foreign_currency), config.foreign_inverse_rate
        )
        self.assertEqual(
            config._get_pos_conversion_rate(self.foreign_currency, usd), config.foreign_rate
        )

    def test_unknown_currency_has_no_rate(self):
        gbp = self.env.ref("base.GBP")
        self.assertEqual(self.usd_config._get_pos_conversion_rate(gbp, self.eur), 0.0)
        self.assertEqual(self.usd_config._get_pos_conversion_rate(self.usd_config.currency_id, gbp), 0.0)

    def test_without_rate_of_the_day_the_tender_currency_cannot_be_converted(self):
        self.env["res.currency.rate"].search([("currency_id", "=", self.eur.id)]).unlink()
        self.usd_config.invalidate_recordset(["tender_currency_rates"])
        self.assertEqual(
            self.usd_config.tender_currency_rates[str(self.eur.id)],
            {"foreign_rate": 0.0, "foreign_inverse_rate": 0.0},
        )
        self.assertEqual(self.usd_config._convert(100.0, self.eur, self.usd_config.currency_id), 0.0)

    # ------------------------------------------------------------------
    # Validaciones del método
    # ------------------------------------------------------------------
    def test_tender_currency_must_be_a_third_currency(self):
        for currency in (self.company.currency_id, self.foreign_currency):
            with self.assertRaises(ValidationError):
                self.split_bank_method.tender_currency_id = currency

    def test_tender_currency_is_not_compatible_with_foreign_currency_flag(self):
        with self.assertRaises(ValidationError):
            self.split_bank_method.write({"is_foreign_currency": True, "tender_currency_id": self.eur.id})

    def test_cross_journal_must_be_in_the_tender_currency(self):
        self.assertNotEqual(self.bank_journal.currency_id, self.eur)
        with self.assertRaises(ValidationError):
            self.split_bank_method.write(
                {
                    "is_foreign_currency": False,
                    "tender_currency_id": self.eur.id,
                    "cross_journal": self.bank_journal.id,
                }
            )

    def test_first_cash_method_cannot_be_in_a_tender_currency(self):
        self.eur_method.sequence = -1
        self.usd_config.invalidate_recordset(["payment_method_ids"])
        with self.assertRaises(ValidationError):
            self.usd_config._check_tender_cash_methods_order()

    # ------------------------------------------------------------------
    # Pagos
    # ------------------------------------------------------------------
    def test_payment_gets_the_tender_currency_of_its_method(self):
        session = self._new_session()
        order = self._eur_order(session, amount=116.0, tender_amount=100.0)
        payment = order.payment_ids
        self.assertEqual(payment.tender_currency_id, self.eur)
        self.assertEqual(payment.tender_amount, 100.0)

    def test_payment_without_tender_amount_takes_its_conversion(self):
        session = self._new_session()
        order = self._eur_order(session, amount=116.0, tender_amount=0.0)
        self.assertEqual(order.payment_ids.tender_amount, 100.0)

    def test_tender_amount_takes_the_sign_of_the_amount(self):
        session = self._new_session()
        order = self._eur_order(session, amount=-116.0, tender_amount=100.0)
        order._align_foreign_signs()
        self.assertEqual(order.payment_ids.tender_amount, -100.0)

    def test_refund_tender_rate_is_the_rate_the_euros_were_collected_at(self):
        session = self._new_session()
        order = self._eur_order(session, amount=116.0, tender_amount=100.0)
        rates = self.env["pos.order"].get_refund_tender_rates(order.ids)
        self.assertAlmostEqual(rates[self.eur.id], 1.16, places=9)
        self.assertEqual(self.env["pos.order"].get_refund_tender_rates([]), {})

    # ------------------------------------------------------------------
    # Carga al PdV
    # ------------------------------------------------------------------
    def test_pos_loads_the_tender_currency(self):
        domain = self.env["res.currency"]._load_pos_data_domain({"product.pricelist": []}, self.usd_config)
        currencies = self.env["res.currency"].search(domain)
        self.assertIn(self.eur, currencies)
        self.assertIn(
            "tender_currency_id", self.env["pos.payment.method"]._load_pos_data_fields(self.usd_config)
        )

    def test_currencies_are_always_loaded_whole(self):
        currency = self.env["res.currency"].with_context(pos_last_server_date="2026-01-01 00:00:00")
        self.assertFalse(currency._last_server_date_to_load())

    # ------------------------------------------------------------------
    # Cruce al diario real en la moneda de cobro
    # ------------------------------------------------------------------
    def test_cash_sale_cross_move_carries_the_euros_on_the_eur_journal(self):
        session = self._new_session().with_company(self.company)
        order = self._eur_order(session, amount=116.0, tender_amount=100.0)
        payment = order.payment_ids

        session._validate_cross_move()

        move = self._cross_moves()
        self.assertEqual(len(move), 1)
        eur_leg = move.line_ids.filtered(lambda l: l.account_id == self.account_eur_suspense)
        transit_leg = move.line_ids.filtered(lambda l: l.account_id == self.account_transit_suspense)
        self.assertEqual(eur_leg.currency_id, self.eur)
        self.assertAlmostEqual(eur_leg.credit, 116.0, places=2)
        self.assertAlmostEqual(eur_leg.amount_currency, -100.0, places=2)
        self.assertAlmostEqual(eur_leg.foreign_credit, payment.foreign_amount, places=2)
        self.assertAlmostEqual(transit_leg.debit, 116.0, places=2)
        self.assertAlmostEqual(transit_leg.foreign_debit, payment.foreign_amount, places=2)

    def test_split_cash_sale_crosses_each_payment_with_its_euros(self):
        self.eur_method.split_transactions = True
        session = self._new_session().with_company(self.company)
        self._eur_order(session, amount=116.0, tender_amount=100.0, name="OL/EUR/1")
        self._eur_order(session, amount=58.0, tender_amount=50.0, name="OL/EUR/2")

        session._validate_cross_move()

        eur_legs = self._cross_moves().line_ids.filtered(
            lambda l: l.account_id == self.account_eur_suspense
        )
        self.assertEqual(sorted(eur_legs.mapped("amount_currency")), [-100.0, -50.0])

    def test_bank_method_in_tender_currency_lands_on_the_real_eur_account(self):
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session, method=self.eur_bank_method, amount=116.0, tax_amount=0.0, name="OL/EUR/BANK"
        )
        order.payment_ids.write({"tender_amount": 100.0})
        order._set_payment_tender_values()

        session._validate_cross_move()

        eur_leg = self._cross_moves().line_ids.filtered(lambda l: l.account_id == self.account_eur_cash)
        transit_leg = self._cross_moves().line_ids.filtered(
            lambda l: l.account_id == self.account_transit_bank
        )
        self.assertEqual(eur_leg.currency_id, self.eur)
        self.assertAlmostEqual(eur_leg.debit, 116.0, places=2)
        self.assertAlmostEqual(eur_leg.amount_currency, 100.0, places=2)
        self.assertAlmostEqual(transit_leg.credit, 116.0, places=2)

    def test_methods_without_tender_currency_keep_their_cross_move(self):
        """La moneda de cobro solo se pasa a los cruces de sus métodos: un
        método en la alterna sigue con ``amount_currency`` en la alterna."""
        session = self._new_session()
        self.assertEqual(
            session._get_cross_currency_amount_kwargs(self.base_cash_method, self.env["pos.payment"]), {}
        )
        self.assertEqual(
            session._get_cross_currency_amount_kwargs(self.eur_method, self.env["pos.payment"]),
            {"currency_amount": 0.0},
        )
