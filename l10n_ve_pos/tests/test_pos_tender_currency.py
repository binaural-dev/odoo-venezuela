"""Métodos de pago en una tercera moneda (moneda de cobro, p. ej. EUR) — tarea 86066.

La caja está en la moneda de la compañía y la alterna es la de siempre; un
método con ``tender_currency_id`` se cobra en una tercera moneda: el motor de
conversión (``pos.config._get_pos_conversion_rate``) conoce su tasa del día,
cada pago guarda lo cobrado en esa moneda (``tender_amount``) y el cruce al
diario real en esa moneda lleva ese monto como ``amount_currency``.

Las pruebas corren en dos compañías (ver ``TestPosSessionAccountingBase``):

- ``TestPosTenderCurrency``: la del fixture de siempre, en USD con VEF de
  alterna;
- ``TestPosTenderCurrencyBsCompany``: el escenario real, la compañía en Bs con
  USD de alterna.

En las dos la tercera moneda es EUR.
"""

from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "tender_currency")
class TestPosTenderCurrency(TestPosSessionAccountingBase):
    # Moneda de la compañía por EUR (1 EUR = 1,16 USD).
    EUR_RATE = 1.16
    # `rate` de la alterna del día (alterna por unidad de la compañía) y tasa
    # de los pagos (multiplicador compañía → alterna de `_create_paid_order`).
    FOREIGN_RATE_OF_DAY = 40.0
    PAYMENT_FOREIGN_RATE = 36.5

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.local = cls.company.currency_id
        cls._create_rate_of_day(cls.FOREIGN_RATE_OF_DAY)
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.context_today(cls.env.user),
                "currency_id": cls.eur.id,
                "company_id": cls.company.id,
                "rate": 1 / cls.EUR_RATE,
            }
        )
        # 100 € y 50 € en la moneda de la compañía, a la tasa del día.
        cls.eur_100_local = cls.local.round(100 * cls.EUR_RATE)
        cls.eur_50_local = cls.local.round(50 * cls.EUR_RATE)
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

        # Caja en la moneda de la compañía: diarios sin moneda.
        cls.account_transit = account("T Metodo EUR", "100087T", "asset_cash")
        cls.account_transit_suspense = account("T Transitoria metodo EUR", "190087T")
        base_cash_journal = Journal.create(
            {
                "name": "T Efectivo local", "type": "cash", "code": "TEC86",
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
            {"name": "T Efectivo local", "company_id": cls.company.id, "journal_id": base_cash_journal.id}
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
                "name": "T Caja local con EUR",
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

    def _eur_order(self, session, amount, tender_amount, foreign_rate=None, name="OL/EUR"):
        order = self._create_paid_order(
            session, method=self.eur_method, amount=amount, tax_amount=0.0,
            foreign_rate=foreign_rate or self.PAYMENT_FOREIGN_RATE, name=name,
        )
        order.payment_ids.write({"tender_amount": tender_amount})
        order._set_payment_tender_values()
        order._align_foreign_signs()
        return order

    def _draft_order(self, session, amount, name="OL/EUR/DRAFT"):
        """Orden sin pagos de un producto por ``amount``, sin impuesto (la que
        se cobra desde el backend con ``pos.make.payment``)."""
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": amount * self.PAYMENT_FOREIGN_RATE,
                "foreign_currency_rate": self.PAYMENT_FOREIGN_RATE,
                "lines": [
                    Command.create(
                        {
                            "name": name,
                            "product_id": self.product.id,
                            "price_unit": amount,
                            "qty": 1.0,
                            "price_subtotal": amount,
                            "price_subtotal_incl": amount,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
                "amount_total": amount,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )

    def _pay_from_backend(self, order, method, amount=None):
        """``pos.make.payment`` (cobro o reembolso desde el backend). El
        albarán no es parte de la prueba: la compañía del fixture no tiene
        el almacén completo."""
        wizard_vals = {"payment_method_id": method.id}
        if amount is not None:
            wizard_vals["amount"] = amount
        wizard = (
            self.env["pos.make.payment"]
            .with_context(active_id=order.id)
            .create(wizard_vals)
        )
        with patch.object(type(order), "_create_order_picking", lambda self: None):
            wizard.check()
        return order.payment_ids.filtered(lambda p: p.payment_method_id == method)

    def _paid_eur_sale(self, session, amount, tender_amount, name):
        """Venta cobrada en € a la tasa ``amount / tender_amount`` (no la del
        día), procesada como en el backend."""
        sale = self._draft_order(session, amount, name=name)
        sale.add_payment({
            "pos_order_id": sale.id,
            "amount": amount,
            "payment_method_id": self.eur_method.id,
            "tender_amount": tender_amount,
        })
        with patch.object(type(sale), "_create_order_picking", lambda self: None):
            sale._process_saved_order(False)
        return sale

    def _drop_eur_rate_of_the_day(self):
        self.env["res.currency.rate"].search([("currency_id", "=", self.eur.id)]).unlink()
        self.usd_config.invalidate_recordset(["tender_currency_rates"])

    def _cross_moves(self):
        return self.env["account.move"].search(
            [("journal_id", "=", self.cross_account_journal.id), ("company_id", "=", self.company.id)]
        )

    # ------------------------------------------------------------------
    # Motor de conversión
    # ------------------------------------------------------------------
    def test_config_exposes_the_rates_of_the_tender_currency(self):
        rates = self.usd_config.tender_currency_rates[str(self.eur.id)]
        self.assertAlmostEqual(rates["foreign_rate"], self.EUR_RATE, places=6)
        self.assertAlmostEqual(rates["foreign_inverse_rate"], 1 / self.EUR_RATE, places=9)

    def test_rates_are_the_ones_of_the_company_of_the_pos(self):
        """``compute_rate`` busca las tasas de ``env.company``: el compute las
        pide con la compañía de la caja, sin depender de la compañía activa del
        usuario (aquí, la principal, sin tasa de EUR para hoy)."""
        self.assertNotEqual(self.env.company, self.company)
        config = self.usd_config.with_company(self.env.company)
        config.invalidate_recordset(["tender_currency_rates"])
        self.assertAlmostEqual(
            config.tender_currency_rates[str(self.eur.id)]["foreign_rate"], self.EUR_RATE, places=6
        )

    def test_conversion_between_pos_currency_and_tender_currency(self):
        config = self.usd_config
        local = config.currency_id
        self.assertAlmostEqual(config._get_pos_conversion_rate(self.eur, local), self.EUR_RATE, places=6)
        self.assertAlmostEqual(
            config._get_pos_conversion_rate(local, self.eur), 1 / self.EUR_RATE, places=9
        )
        self.assertEqual(config._convert(100.0, self.eur, local), self.eur_100_local)
        self.assertEqual(config._convert(self.eur_100_local, local, self.eur), 100.0)

    def test_tender_to_foreign_goes_through_the_pos_currency_without_rounding_the_rate(self):
        # La tasa alterna de la caja (``_compute_rate``) sale de la compañía activa.
        config = self.usd_config.with_company(self.company)
        config.invalidate_recordset(["foreign_rate", "foreign_inverse_rate"])
        self.assertTrue(config.foreign_inverse_rate)
        expected = config.tender_currency_rates[str(self.eur.id)]["foreign_rate"] * (
            config.foreign_inverse_rate
        )
        self.assertAlmostEqual(
            config._get_pos_conversion_rate(self.eur, self.foreign_currency), expected, places=12
        )
        self.assertEqual(
            config._convert(10.0, self.eur, self.foreign_currency),
            self.foreign_currency.round(10.0 * expected),
        )

    def test_main_foreign_pair_is_unchanged(self):
        config = self.usd_config
        local = config.currency_id
        self.assertEqual(
            config._get_pos_conversion_rate(local, self.foreign_currency), config.foreign_inverse_rate
        )
        self.assertEqual(
            config._get_pos_conversion_rate(self.foreign_currency, local), config.foreign_rate
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
    # Validaciones del método y de la caja
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
        with self.assertRaisesRegex(ValidationError, "must be in"):
            self.eur_method.cross_journal = self.bank_journal

    def test_tender_currency_requires_both_cross_journals(self):
        """Sin sus dos diarios de cruce, ``_is_cross_move_eligible`` omitiría
        en silencio el cruce y los euros nunca llegarían a la caja real."""
        for missing in ("cross_journal", "cross_account_journal"):
            with (
                self.subTest(missing=missing),
                self.assertRaisesRegex(ValidationError, "Cross Account Journal"),
                self.env.cr.savepoint(),
            ):
                self.eur_method.write({missing: False})
        with self.assertRaisesRegex(ValidationError, "Cross Account Journal"):
            self.env["pos.payment.method"].create(
                {
                    "name": "T EUR sin cruce",
                    "company_id": self.company.id,
                    "journal_id": self.eur_method.journal_id.id,
                    "tender_currency_id": self.eur.id,
                }
            )

    def test_first_cash_method_cannot_be_in_a_tender_currency(self):
        self.eur_method.sequence = -1
        self.usd_config.invalidate_recordset(["payment_method_ids"])
        with self.assertRaises(ValidationError):
            self.usd_config._check_tender_cash_methods_order()

    def test_tender_currency_only_in_a_pos_in_the_company_currency(self):
        """Las tasas de la moneda de cobro son contra la moneda de la
        compañía: una caja en otra moneda (aquí ``config``, con el diario de
        ventas en la alterna) no acepta métodos con moneda de cobro, ni al
        agregarlos a la caja ni al ponerle la moneda a un método de la caja."""
        self.assertNotEqual(self.config.currency_id, self.company.currency_id)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.config.payment_method_ids |= self.eur_bank_method
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.split_bank_method.write(
                {
                    "is_foreign_currency": False,
                    "tender_currency_id": self.eur.id,
                    "cross_journal": self.eur_journal.id,
                }
            )
        # En la caja en la moneda de la compañía, sí.
        self.assertEqual(self.usd_config.currency_id, self.company.currency_id)
        self.assertIn(self.eur_method, self.usd_config.payment_method_ids)

    # ------------------------------------------------------------------
    # Pagos
    # ------------------------------------------------------------------
    def test_payment_gets_the_tender_currency_of_its_method(self):
        session = self._new_session()
        order = self._eur_order(session, amount=self.eur_100_local, tender_amount=100.0)
        payment = order.payment_ids
        self.assertEqual(payment.tender_currency_id, self.eur)
        self.assertEqual(payment.tender_amount, 100.0)

    def test_payment_without_tender_amount_takes_its_conversion(self):
        session = self._new_session()
        order = self._eur_order(session, amount=self.eur_100_local, tender_amount=0.0)
        self.assertEqual(order.payment_ids.tender_amount, 100.0)

    def test_tender_amount_takes_the_sign_of_the_amount(self):
        session = self._new_session()
        order = self._eur_order(session, amount=-self.eur_100_local, tender_amount=100.0)
        self.assertEqual(order.payment_ids.tender_amount, -100.0)

    def test_refund_tender_rate_is_the_rate_the_euros_were_collected_at(self):
        session = self._new_session()
        order = self._eur_order(session, amount=self.eur_100_local, tender_amount=100.0)
        rates = self.env["pos.order"].get_refund_tender_rates(order.ids)
        self.assertAlmostEqual(rates[self.eur.id], self.eur_100_local / 100.0, places=9)
        self.assertEqual(self.env["pos.order"].get_refund_tender_rates([]), {})

    def _sync_payload(self, session, uuid, payments):
        local = self.eur_100_local + self.eur_50_local
        return {
            "id": False,
            "name": f"Order/{uuid}",
            "uuid": uuid,
            "access_token": f"token-{uuid}",
            "session_id": session.id,
            "company_id": self.company.id,
            "config_id": self.usd_config.id,
            "currency_id": self.local.id,
            "pricelist_id": self.company.partner_id.property_product_pricelist.id,
            "partner_id": False,
            "date_order": False,
            "state": "draft",
            "amount_total": local,
            "amount_tax": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "foreign_amount_total": local * self.PAYMENT_FOREIGN_RATE,
            "foreign_currency_rate": self.PAYMENT_FOREIGN_RATE,
            "lines": [
                [0, 0, {
                    "name": f"OL/{uuid}",
                    "uuid": f"line-{uuid}",
                    "product_id": self.product.id,
                    "price_unit": local,
                    "discount": 0.0,
                    "qty": 1.0,
                    "price_subtotal": local,
                    "price_subtotal_incl": local,
                    "tax_ids": [(6, 0, [])],
                }],
            ],
            "payment_ids": [
                [0, 0, dict(
                    {
                        "name": f"Payment {index}",
                        "uuid": f"payment-{uuid}-{index}",
                        "payment_method_id": self.eur_method.id,
                        "payment_date": fields.Datetime.now(),
                        "foreign_rate": self.PAYMENT_FOREIGN_RATE,
                    },
                    **payment,
                )]
                for index, payment in enumerate(payments)
            ],
            "last_order_preparation_change": "{}",
        }

    def test_sync_from_ui_sets_the_tender_currency_of_the_payments(self):
        """La sincronización real del PdV (``sync_from_ui`` →
        ``_process_payment_lines`` → ``_process_saved_order``), sin llamar a
        mano a ``_set_payment_tender_values``: el PdV manda ``tender_amount``
        y no la moneda, que el servidor toma del método. Un pago de un bundle
        anterior (sin ``tender_amount``) recibe su conversión."""
        session = self._new_session()
        payload = self._sync_payload(session, "86066-sync", [
            {
                "amount": self.eur_100_local,
                "foreign_amount": self.eur_100_local * self.PAYMENT_FOREIGN_RATE,
                "tender_amount": 100.0,
            },
            {
                "amount": self.eur_50_local,
                "foreign_amount": self.eur_50_local * self.PAYMENT_FOREIGN_RATE,
            },
        ])

        self.env["pos.order"].sync_from_ui([payload])

        order = self.env["pos.order"].search([("uuid", "=", "86066-sync")])
        self.assertEqual(len(order.payment_ids), 2)
        self.assertEqual(order.payment_ids.tender_currency_id, self.eur)
        self.assertEqual(
            sorted(order.payment_ids.mapped("tender_amount")), [50.0, 100.0]
        )

    def test_backend_payment_wizard_sets_the_tender_values(self):
        """``pos.make.payment`` no pasa por ``_process_payment_lines``: el pago
        en € queda con su moneda y su monto en € igual (``_process_saved_order``)."""
        session = self._new_session()
        order = self._draft_order(session, self.eur_100_local)

        payment = self._pay_from_backend(order, self.eur_method)

        self.assertEqual(order.state, "paid")
        self.assertEqual(payment.amount, self.eur_100_local)
        self.assertEqual(payment.tender_currency_id, self.eur)
        self.assertEqual(payment.tender_amount, 100.0)

    def test_backend_refund_returns_the_euros_at_the_original_rate(self):
        """Un reembolso desde el backend devuelve los euros a la tasa con la
        que se cobraron (``get_refund_tender_rates``), no a la del día, igual
        que el PdV: la venta se cobró a 80 € por ``eur_100_local``."""
        session = self._new_session()
        sale = self._paid_eur_sale(session, self.eur_100_local, 80.0, "OL/EUR/SALE")
        self.assertEqual(sale.payment_ids.tender_amount, 80.0)

        refund = sale._refund()
        payment = self._pay_from_backend(refund, self.eur_method)

        self.assertEqual(payment.amount, -self.eur_100_local)
        self.assertEqual(payment.tender_currency_id, self.eur)
        self.assertEqual(payment.tender_amount, -80.0)

    def test_backend_refund_of_two_sales_takes_the_rate_of_both(self):
        """Un reembolso con líneas de dos ventas cobradas en € a tasas
        distintas (80 € por ``eur_100_local`` y 50 € por ``eur_50_local``)
        devuelve los 130 € a la tasa de las dos, como el PdV con
        ``originOrderIds``, no solo a la de la primera
        (``refunded_order_id``), que daría 120 €. El PdV no puede armarlo
        (``sync_from_ui`` del core rechaza un reembolso de varias órdenes):
        se arma aquí moviendo las líneas con el ORM."""
        session = self._new_session()
        sale_1 = self._paid_eur_sale(session, self.eur_100_local, 80.0, "OL/EUR/S1")
        sale_2 = self._paid_eur_sale(session, self.eur_50_local, 50.0, "OL/EUR/S2")
        refund = sale_1._refund()
        other_refund = sale_2._refund()
        other_refund.lines.order_id = refund
        refund.amount_total += other_refund.amount_total
        self.assertEqual(refund.lines.refunded_orderline_id.order_id, sale_1 | sale_2)
        self.assertEqual(refund.refunded_order_id, sale_1)

        payment = self._pay_from_backend(refund, self.eur_method, amount=refund.amount_total)

        self.assertAlmostEqual(payment.amount, -(self.eur_100_local + self.eur_50_local), places=2)
        self.assertEqual(payment.tender_amount, -130.0)

    def test_backend_payment_without_rate_of_the_day_is_refused(self):
        """Hallazgo A1: sin tasa del día del EUR, el PdV no agrega la línea;
        el cobro desde el backend tampoco se acepta (si no, quedaría un pago
        con 0 € en el cajón y en el cruce)."""
        session = self._new_session()
        order = self._draft_order(session, self.eur_100_local)
        self._drop_eur_rate_of_the_day()

        with self.assertRaisesRegex(UserError, "no exchange rate of the day for EUR"):
            self._pay_from_backend(order, self.eur_method)

        self.assertFalse(order.payment_ids)
        self.assertEqual(order.state, "draft")
        # Los demás métodos se cobran igual.
        self._pay_from_backend(order, self.base_cash_method)
        self.assertEqual(order.state, "paid")

    def test_sync_without_rate_of_the_day_is_not_blocked(self):
        """Una orden de un bundle anterior (sin ``tender_amount``) que llega
        sin tasa del día del EUR se sincroniza igual, con 0 € y un aviso en el
        log: el bloqueo es del PdV y del cobro desde el backend."""
        session = self._new_session()
        self._drop_eur_rate_of_the_day()
        local = self.eur_100_local + self.eur_50_local
        payload = self._sync_payload(session, "86066-norate", [
            {"amount": local, "foreign_amount": local * self.PAYMENT_FOREIGN_RATE},
        ])
        payload.update({"state": "paid", "amount_paid": local})

        Order = type(self.env["pos.order"])
        with (
            self.assertLogs("odoo.addons.l10n_ve_pos.models.pos_order", "WARNING") as logs,
            # El albarán no es parte de la prueba (ver ``_pay_from_backend``).
            patch.object(Order, "_create_order_picking", lambda self: None),
        ):
            self.env["pos.order"].sync_from_ui([payload])

        order = self.env["pos.order"].search([("uuid", "=", "86066-norate")])
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.payment_ids.tender_currency_id, self.eur)
        self.assertEqual(order.payment_ids.tender_amount, 0.0)
        self.assertIn("without exchange rate of the day for EUR", logs.output[0])

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
    def _eur_legs(self, move=None):
        """Líneas de la transitoria de la caja real en EUR (cruce de efectivo,
        ``use_suspense``) y de la transitoria del método."""
        moves = move or self._cross_moves()
        return (
            moves.line_ids.filtered(lambda l: l.account_id == self.account_eur_suspense),
            moves.line_ids.filtered(lambda l: l.account_id == self.account_transit_suspense),
        )

    def assertCoherentSigns(self, lines):
        """Cada línea con ``amount_currency`` y saldo del mismo signo (lo que
        exige ``account_move_line_check_amount_currency_balance_sign``), también
        en la alterna (``foreign_debit``/``foreign_credit`` van del lado del
        saldo)."""
        for line in lines:
            self.assertGreaterEqual(line.amount_currency * line.balance, 0.0, line.name)
            if line.debit:
                self.assertFalse(line.foreign_credit)
            if line.credit:
                self.assertFalse(line.foreign_debit)

    def test_cash_sale_cross_move_carries_the_euros_on_the_eur_journal(self):
        session = self._new_session().with_company(self.company)
        order = self._eur_order(session, amount=self.eur_100_local, tender_amount=100.0)
        payment = order.payment_ids

        session._validate_cross_move()

        move = self._cross_moves()
        self.assertEqual(len(move), 1)
        eur_leg, transit_leg = self._eur_legs(move)
        self.assertEqual(eur_leg.currency_id, self.eur)
        self.assertAlmostEqual(eur_leg.credit, self.eur_100_local, places=2)
        self.assertAlmostEqual(eur_leg.amount_currency, -100.0, places=2)
        self.assertAlmostEqual(eur_leg.foreign_credit, payment.foreign_amount, places=2)
        self.assertAlmostEqual(transit_leg.debit, self.eur_100_local, places=2)
        self.assertAlmostEqual(transit_leg.foreign_debit, payment.foreign_amount, places=2)

    def test_split_cash_sale_crosses_each_payment_with_its_euros(self):
        self.eur_method.split_transactions = True
        session = self._new_session().with_company(self.company)
        self._eur_order(session, amount=self.eur_100_local, tender_amount=100.0, name="OL/EUR/1")
        self._eur_order(session, amount=self.eur_50_local, tender_amount=50.0, name="OL/EUR/2")

        session._validate_cross_move()

        eur_legs, _transit = self._eur_legs()
        self.assertEqual(sorted(eur_legs.mapped("amount_currency")), [-100.0, -50.0])

    def test_bank_method_in_tender_currency_lands_on_the_real_eur_account(self):
        session = self._new_session().with_company(self.company)
        order = self._create_paid_order(
            session, method=self.eur_bank_method, amount=self.eur_100_local, tax_amount=0.0,
            foreign_rate=self.PAYMENT_FOREIGN_RATE, name="OL/EUR/BANK",
        )
        order.payment_ids.write({"tender_amount": 100.0})
        order._set_payment_tender_values()

        session._validate_cross_move()

        eur_leg = self._cross_moves().line_ids.filtered(lambda l: l.account_id == self.account_eur_cash)
        transit_leg = self._cross_moves().line_ids.filtered(
            lambda l: l.account_id == self.account_transit_bank
        )
        self.assertEqual(eur_leg.currency_id, self.eur)
        self.assertAlmostEqual(eur_leg.debit, self.eur_100_local, places=2)
        self.assertAlmostEqual(eur_leg.amount_currency, 100.0, places=2)
        self.assertAlmostEqual(transit_leg.credit, self.eur_100_local, places=2)

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

    def test_cross_without_the_euros_converts_the_amount_at_the_rate_of_the_day(self):
        """Un llamador que no pasa ``currency_amount`` (un módulo con la firma
        anterior de ``_create_cross_move_for``) no pone la moneda de la caja
        como euros en el diario en EUR: la convierte a la tasa del día."""
        session = self._new_session().with_company(self.company)

        move = session._create_cross_move_for(
            self.eur_method,
            amount=self.eur_100_local,
            foreign_amount=self.eur_100_local * self.PAYMENT_FOREIGN_RATE,
            foreign_rate=self.PAYMENT_FOREIGN_RATE,
            partner=self.env["res.partner"],
            date=fields.Datetime.now(),
            ref="sin currency_amount",
            use_suspense=True,
        )

        eur_leg, _transit = self._eur_legs(move)
        self.assertAlmostEqual(eur_leg.amount_currency, -100.0, places=2)

    # ------------------------------------------------------------------
    # Cruce combinado: entradas y salidas en dos patas (hallazgo 6)
    # ------------------------------------------------------------------
    def test_combine_sale_and_refund_at_another_rate_cross_in_two_legs(self):
        """Venta de 20 € a 50 (1.000) y reembolso de 25 € a 30 (−750): el neto
        en la moneda de la caja (+250) y en euros (−5) tienen signos opuestos.
        Un solo par de líneas con los netos violaba
        ``account_move_line_check_amount_currency_balance_sign`` y tumbaba el
        cierre. Ahora es UN asiento con una pata de entradas y otra de
        salidas, cada línea con signos coherentes, y la caja real en EUR
        recibe el neto de los euros."""
        session = self._new_session().with_company(self.company)
        self._eur_order(session, amount=1000.0, tender_amount=20.0, name="OL/EUR/SALE")
        self._eur_order(session, amount=-750.0, tender_amount=25.0, name="OL/EUR/REFUND")

        session._validate_cross_move()

        move = self._cross_moves()
        self.assertEqual(len(move), 1, "un asiento por método y sesión")
        self.assertEqual(len(move.line_ids), 4, "dos líneas por pata")
        self.assertCoherentSigns(move.line_ids)
        eur_legs, transit_legs = self._eur_legs(move)
        self.assertEqual(sorted(eur_legs.mapped("amount_currency")), [-20.0, 25.0])
        self.assertAlmostEqual(sum(eur_legs.mapped("balance")), -250.0, places=2)
        self.assertAlmostEqual(sum(eur_legs.mapped("amount_currency")), 5.0, places=2)
        self.assertAlmostEqual(sum(transit_legs.mapped("balance")), 250.0, places=2)

    def test_combine_each_leg_carries_the_rate_of_its_payments(self):
        """Hallazgo S7: las líneas de la pata de salidas se arman con la tasa
        de sus pagos (la del reembolso, la de su venta original), no con la de
        la venta del día. Es informativa: la línea guardada toma la del asiento
        (``account.move.line.foreign_rate`` es un related de
        ``l10n_ve_accountant``) y sus montos alternos son los de sus pagos."""
        refund_rate = self.PAYMENT_FOREIGN_RATE * 2
        session = self._new_session().with_company(self.company)
        self._eur_order(session, amount=1000.0, tender_amount=20.0, name="OL/EUR/SALE")
        self._eur_order(
            session, amount=-750.0, tender_amount=25.0, foreign_rate=refund_rate,
            name="OL/EUR/REFUND",
        )
        Session = type(session)

        with patch.object(
            Session, "_get_cross_move_line_vals", autospec=True,
            side_effect=Session._get_cross_move_line_vals,
        ) as line_vals:
            session._validate_cross_move()

        rate_by_amount = {call.args[2]: call.args[4] for call in line_vals.call_args_list}
        self.assertEqual(rate_by_amount, {1000.0: self.PAYMENT_FOREIGN_RATE, -750.0: refund_rate})

    def test_combine_zero_local_net_still_crosses_the_euros(self):
        """Neto 0 en la moneda de la caja con euros de diferencia: antes no se
        creaba el cruce y esos euros nunca llegaban al diario real."""
        session = self._new_session().with_company(self.company)
        self._eur_order(session, amount=1000.0, tender_amount=20.0, name="OL/EUR/SALE")
        self._eur_order(session, amount=-1000.0, tender_amount=25.0, name="OL/EUR/REFUND")

        session._validate_cross_move()

        move = self._cross_moves()
        self.assertEqual(len(move), 1)
        self.assertCoherentSigns(move.line_ids)
        eur_legs, _transit = self._eur_legs(move)
        self.assertAlmostEqual(sum(eur_legs.mapped("balance")), 0.0, places=2)
        self.assertAlmostEqual(sum(eur_legs.mapped("amount_currency")), 5.0, places=2)

    def test_combine_all_nets_zero_creates_nothing(self):
        """Solo cuando los netos en la caja, la alterna y los euros dan todos
        cero no se crea el cruce."""
        session = self._new_session().with_company(self.company)
        self._eur_order(session, amount=1000.0, tender_amount=20.0, name="OL/EUR/SALE")
        self._eur_order(session, amount=-1000.0, tender_amount=20.0, name="OL/EUR/REFUND")

        session._validate_cross_move()

        self.assertFalse(self._cross_moves())


@tagged("post_install", "-at_install", "l10n_ve_pos", "tender_currency")
class TestPosTenderCurrencyBsCompany(TestPosTenderCurrency):
    """El escenario real: la compañía en Bs (VEF) con USD de alterna y EUR de
    tercera moneda, con las tasas de la base de prueba de la tarea
    (860,4321 Bs/$ y 1.003,8765 Bs/€). Corre todas las pruebas de arriba."""

    # El cargador de pruebas de Odoo 19 solo toma los métodos definidos en la
    # propia clase, salvo con esta marca.
    allow_inherited_tests_method = True

    company_currency_name = "VEF"
    foreign_currency_name = "USD"
    EUR_RATE = 1003.8765
    # `rate` de USD en la compañía en Bs: dólares por bolívar.
    FOREIGN_RATE_OF_DAY = 1 / 860.4321
    PAYMENT_FOREIGN_RATE = 1 / 860.4321
