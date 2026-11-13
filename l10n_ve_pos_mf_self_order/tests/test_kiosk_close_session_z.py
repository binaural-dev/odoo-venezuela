"""Cierre de sesión con Reporte Z desde el panel de Debug del Kiosko (ticket 16406).

Prueba las rutas públicas de ``controllers/main.py`` llamando a los métodos del
controlador con ``_verify_pos_config`` parcheado (como
``l10n_ve_pos_self_order/tests/test_kiosk_public_routes.py``), con un usuario
de Kiosko sin permisos contables, que es como corre en Monfarmacia:

* ``close_session/check``: órdenes de la sesión sin número fiscal.
* ``report_z``: sincroniza la Z con los mismos métodos que la caja y solo marca
  las facturas de una máquina con la que imprimió la caja.
* ``close_session``: no cierra con órdenes pendientes; si el cierre nativo
  falla, la sesión queda abierta.
* Las tres rutas rechazan las cajas en modo ``mobile`` (QR de mesa) y, por
  HTTP real (``TestKioskCloseSessionZHttp``), un token inválido.
"""

import json
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from werkzeug.exceptions import Unauthorized

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pos_self_order.controllers.orders import PosSelfOrderController
from odoo.addons.l10n_ve_pos_mf_self_order.controllers.main import (
    L10nVePosMfSelfOrderController,
)

SERIAL = "Z7C0000001"


@tagged("post_install", "-at_install", "l10n_ve_pos_mf_self_order")
class TestKioskCloseSessionZ(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Kiosk Close Z Co",
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
        cls.company.write({"foreign_currency_id": vef.id})
        admin = cls.env.ref("base.user_admin")
        admin.company_ids |= cls.company

        account = cls.env["account.account"].create(
            {
                "name": "Kiosk Close Z Income",
                "code": "400000KCZ",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        # l10n_ve_accountant exige impuestos en el producto o por defecto en la
        # compañía.
        tax_group = cls.env["account.tax.group"].create(
            {"name": "Kiosk Close Z Tax Group", "company_id": cls.company.id}
        )
        tax = cls.env["account.tax"].create(
            {
                "name": "Kiosk Close Z Tax",
                "amount": 0.0,
                "type_tax_use": "sale",
                "tax_group_id": tax_group.id,
                "company_id": cls.company.id,
            }
        )
        cls.company.write(
            {"account_sale_tax_id": tax.id, "account_purchase_tax_id": tax.id}
        )
        category = cls.env["product.category"].create(
            {
                "name": "Kiosk Close Z Category",
                "property_account_income_categ_id": account.id,
                "property_account_expense_categ_id": account.id,
            }
        )
        cls.product = cls.env["product.product"].with_company(cls.company).create(
            {
                "name": "Kiosk Close Z Product",
                "type": "service",
                "lst_price": 100.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": category.id,
            }
        )
        sale_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk Close Z Sale Journal",
                "type": "sale",
                "code": "KCZSJ",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        # Usuario del Kiosko como el de Monfarmacia: usuario de PdV, sin
        # permisos contables. Las rutas tienen que funcionar con él.
        cls.kiosk_user = cls.env["res.users"].create(
            {
                "name": "Kiosk Close Z User",
                "login": "kiosk_close_z_user",
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("point_of_sale.group_pos_user").id,
                        ]
                    )
                ],
            }
        )

        cls.sale_journal = sale_journal
        # Sin datos demo (CI): el cliente de las facturas se crea aquí.
        cls.partner = cls.env["res.partner"].create(
            {"name": "Kiosk Close Z Customer", "company_id": cls.company.id}
        )
        bank_account = cls.env["account.account"].create(
            {
                "name": "Kiosk Close Z Bank Account",
                "code": "101000KCZ",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        # l10n_ve_accountant exige la cuenta por defecto en los diarios de banco.
        bank_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk Close Z Bank",
                "type": "bank",
                "code": "KCZBK",
                "company_id": cls.company.id,
                "default_account_id": bank_account.id,
            }
        )
        # Método no efectivo (el modo kiosko no admite efectivo), para las
        # órdenes con pago.
        cls.card_method = cls.env["pos.payment.method"].create(
            {
                "name": "Kiosk Close Z Card",
                "journal_id": bank_journal.id,
                "company_id": cls.company.id,
            }
        )

        def _make_config(name, mode="kiosk"):
            config = cls.env["pos.config"].create(
                {
                    "name": name,
                    "company_id": cls.company.id,
                    "currency_id": vef.id,
                    "journal_id": sale_journal.id,
                    "invoice_journal_id": sale_journal.id,
                    "self_ordering_mode": mode,
                    "self_ordering_default_user_id": cls.kiosk_user.id,
                    "payment_method_ids": [(6, 0, [cls.card_method.id])],
                }
            )
            # Sesión abierta como la abre el backend al iniciar el Kiosko
            # (pos.config.action_open_wizard): estado "opened".
            session = cls.env["pos.session"].create(
                {"config_id": config.id, "user_id": admin.id}
            )
            session.set_opening_control(0, "")
            return config

        cls.config = _make_config("Kiosk Close Z A")
        cls.other_config = _make_config("Kiosk Close Z B")
        # Autopedido por QR: su token va impreso en las mesas.
        cls.mobile_config = _make_config("Kiosk Close Z QR", mode="mobile")

    # -- helpers -------------------------------------------------------------

    def _reduced_config(self, config):
        """Lo que devuelve el ``_verify_pos_config`` del core: la caja sin sudo,
        con el usuario y la compañía del Kiosko."""
        return (
            config.sudo(False)
            .with_company(config.company_id)
            .with_user(config.self_ordering_default_user_id)
            .with_context(allowed_company_ids=config.company_id.ids)
        )

    @contextmanager
    def _as_box(self, config):
        """Parchea ``_verify_pos_config`` (lo único que necesita ``request``) y
        ``_()`` del controlador, que fuera de un ``request`` real revienta al
        resolver el idioma."""

        def _passthrough(source, *args, **kwargs):
            return (source % args) if args else source

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    PosSelfOrderController,
                    "_verify_pos_config",
                    return_value=self._reduced_config(config),
                )
            )
            stack.enter_context(
                patch(
                    "odoo.addons.l10n_ve_pos_mf_self_order.controllers.main._",
                    _passthrough,
                )
            )
            yield

    def _call(self, method_name, config=None, **kwargs):
        config = config or self.config
        with self._as_box(config):
            return getattr(L10nVePosMfSelfOrderController(), method_name)(
                access_token=config.access_token, **kwargs
            )

    def _make_order(self, config, state="paid", **vals):
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": config.current_session_id.id,
                "state": state,
                "amount_total": 100.0,
                "amount_tax": 0.0,
                "amount_paid": 100.0 if state != "draft" else 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
                "lines": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "price_unit": 100.0,
                            "qty": 1.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 100.0,
                        }
                    )
                ],
                **vals,
            }
        )

    def _make_invoice(self, serial):
        """Factura de la máquina ``serial`` todavía sin Z."""
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "journal_id": self.sale_journal.id,
                "partner_id": self.partner.id,
                "mf_serial": serial,
            }
        )

    def _add_payment(self, order):
        self.env["pos.payment"].create(
            {"pos_order_id": order.id, "payment_method_id": self.card_method.id, "amount": 100.0}
        )
        return order

    def _z_value(self, serial=SERIAL, counter=12, valid=True):
        return {
            "valid": valid,
            "data": {"_registeredMachineNumber": serial, "_dailyClosureCounter": counter},
        }

    # -- close_session/check -------------------------------------------------

    def test_check_lists_session_orders_without_fiscal_number(self):
        pending = self._make_order(self.config)
        self._make_order(self.config, mf_invoice_number="00000001", fiscal_machine=SERIAL)
        self._make_order(self.config, state="draft")
        self._make_order(self.config, state="cancel")
        self._make_order(self.other_config)

        result = self._call("l10n_ve_kiosk_close_session_check")

        self.assertEqual([o["id"] for o in result["pending_orders"]], [pending.id])
        self.assertEqual(result["pending_orders"][0]["name"], pending.name)
        self.assertFalse(result["pending_orders"][0]["is_invoiced"])

    def test_check_without_pending_orders_is_empty(self):
        self._make_order(self.config, mf_invoice_number="00000001", fiscal_machine=SERIAL)
        result = self._call("l10n_ve_kiosk_close_session_check")
        self.assertEqual(result["pending_orders"], [])

    def test_check_counts_draft_with_payment(self):
        """Un borrador con pago es una orden cobrada a medias, no un carrito:
        bloquea. El borrador sin pago no."""
        charged = self._add_payment(self._make_order(self.config, state="draft"))
        self._make_order(self.config, state="draft")

        result = self._call("l10n_ve_kiosk_close_session_check")

        self.assertEqual([o["id"] for o in result["pending_orders"]], [charged.id])
        self.assertEqual(result["pending_orders"][0]["state"], "draft")

    def test_check_returns_pending_orders_for_the_panel(self):
        """Las pendientes que se resuelven en el panel de Órdenes vienen con sus
        datos para cargarlas en el cliente; el borrador con pago no (el panel no
        lista borradores)."""
        paid = self._make_order(self.config)
        self._add_payment(self._make_order(self.config, state="draft"))

        result = self._call("l10n_ve_kiosk_close_session_check")

        self.assertEqual([o["id"] for o in result["data"]["pos.order"]], [paid.id])
        self.assertEqual(
            [line["order_id"] for line in result["data"]["pos.order.line"]], [paid.id]
        )

    def test_check_returns_existing_report_z(self):
        self.assertFalse(self._call("l10n_ve_kiosk_close_session_check")["report_z"])

        self.config.current_session_id.report_z = "13"

        self.assertEqual(self._call("l10n_ve_kiosk_close_session_check")["report_z"], "13")

    # -- modo mobile (QR de mesa) -------------------------------------------

    def test_routes_reject_mobile_box(self):
        """Con el token de una caja de autopedido por QR ninguna ruta responde:
        ni revisa, ni registra una Z, ni cierra."""
        session = self.mobile_config.current_session_id
        calls = (
            ("l10n_ve_kiosk_close_session_check", {}),
            ("l10n_ve_kiosk_report_z", {"value": self._z_value()}),
            ("l10n_ve_kiosk_close_session", {}),
        )
        for method_name, kwargs in calls:
            with self.assertRaises(Unauthorized, msg=method_name):
                self._call(method_name, config=self.mobile_config, **kwargs)
        self.assertEqual(session.state, "opened")
        self.assertFalse(session.report_z)

    # -- close_session -------------------------------------------------------

    def test_close_refused_with_pending_orders(self):
        pending = self._make_order(self.config)
        session = self.config.current_session_id

        result = self._call("l10n_ve_kiosk_close_session")

        self.assertFalse(result["success"])
        self.assertEqual([o["id"] for o in result["pending_orders"]], [pending.id])
        self.assertEqual(session.state, "opened")

    def test_close_refused_with_draft_with_payment(self):
        charged = self._add_payment(self._make_order(self.config, state="draft"))
        session = self.config.current_session_id

        result = self._call("l10n_ve_kiosk_close_session")

        self.assertFalse(result["success"])
        self.assertEqual(session.state, "opened")
        self.assertTrue(charged.exists())

    def test_close_session_closes_and_drops_carts(self):
        """Sin órdenes pendientes cierra con el cierre nativo del Kiosko, que
        borra los carritos sin pagar (borradores)."""
        cart = self._make_order(self.config, state="draft")
        session = self.config.current_session_id

        result = self._call("l10n_ve_kiosk_close_session")

        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(session.state, "closed")
        self.assertFalse(cart.exists())
        self.assertEqual(self.other_config.current_session_id.state, "opened")

    def test_close_failure_keeps_session_open(self):
        """Si el cierre nativo falla, el error sale de la ruta (el framework
        revierte la petición): la sesión queda abierta y nada se borra."""
        session = self.config.current_session_id
        cart = self._make_order(self.config, state="draft")

        def _fail(config_self):
            config_self.current_session_id.order_ids.filtered(
                lambda o: o.state == "draft"
            ).unlink()
            raise UserError("Cierre rechazado")

        with patch.object(type(self.config), "action_close_kiosk_session", _fail):
            # `assertRaises` de Odoo envuelve en un savepoint y lo revierte, como
            # el framework con la petición (`assertRaisesRegex` no lo hace).
            with self.assertRaises(UserError) as caught:
                self._call("l10n_ve_kiosk_close_session")
        self.assertIn("Cierre rechazado", str(caught.exception))

        self.env.invalidate_all()
        self.assertEqual(session.state, "opened")
        self.assertTrue(cart.exists(), "el fallo revierte todo el cierre")

    def test_close_not_finished_raises(self):
        """Si el cierre nativo no termina (asiento descuadrado: devuelve el
        asistente de diferencias), la ruta no responde éxito."""
        session = self.config.current_session_id

        def _wizard(config_self):
            config_self.current_session_id.write({"state": "closing_control"})
            return {"type": "ir.actions.act_window", "res_model": "pos.close.session.wizard"}

        with patch.object(type(self.config), "action_close_kiosk_session", _wizard):
            with self.assertRaises(UserError):
                self._call("l10n_ve_kiosk_close_session")

        self.env.invalidate_all()
        self.assertEqual(session.state, "opened")

    # -- report_z ------------------------------------------------------------

    def test_report_z_rejects_invalid_data(self):
        session = self.config.current_session_id
        for value in (
            self._z_value(valid=False),
            self._z_value(serial=""),
            self._z_value(counter="12"),
            self._z_value(counter=True),
            {"valid": True},
            "basura",
        ):
            result = self._call("l10n_ve_kiosk_report_z", value=value)
            self.assertFalse(result["success"], value)
        self.assertFalse(session.report_z)

    def test_report_z_syncs_session_and_box_orders(self):
        """Con los mismos métodos que la caja: la sesión guarda el Z (contador +
        1) y las órdenes de la máquina sin Z quedan marcadas."""
        order = self._make_order(
            self.config, mf_invoice_number="00000001", fiscal_machine=SERIAL
        )
        self.invoice = self._make_invoice(SERIAL)
        session = self.config.current_session_id

        result = self._call("l10n_ve_kiosk_report_z", value=self._z_value(counter=12))

        self.assertTrue(result["success"], result.get("error"))
        self.assertEqual(session.report_z, "13")
        self.assertEqual(session.serial_machine, SERIAL)
        self.assertTrue(session.report_z_date)
        self.assertEqual(order.mf_reportz, "13")
        self.assertEqual(self.invoice.mf_reportz, "13", "la factura de la máquina queda con su Z")
        self.assertFalse(self.other_config.current_session_id.report_z)

    def test_report_z_does_not_touch_other_machines(self):
        """Con el token de una caja no se marca el Z de una máquina con la que
        esa caja nunca imprimió; la sesión sí guarda su Z."""
        foreign = self._make_order(
            self.other_config, mf_invoice_number="00000009", fiscal_machine="Z7COTHER01"
        )
        foreign_invoice = self._make_invoice("Z7COTHER01")
        session = self.config.current_session_id

        result = self._call(
            "l10n_ve_kiosk_report_z", value=self._z_value(serial="Z7COTHER01", counter=40)
        )

        self.assertTrue(result["success"], result.get("error"))
        self.assertFalse(foreign.mf_reportz)
        self.assertFalse(foreign_invoice.mf_reportz)
        self.assertEqual(session.report_z, "41")


@tagged("post_install", "-at_install", "l10n_ve_pos_mf_self_order")
class TestKioskCloseSessionZHttp(HttpCase):
    """Validación real del token por JSON-RPC (sin parchear
    ``_verify_pos_config``): token inválido y caja de autopedido por QR."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        pos_user = cls.env["res.users"].create(
            {
                "name": "Kiosk Close Z Http User",
                "login": "kiosk_close_z_http_user",
                "group_ids": [Command.set([cls.env.ref("point_of_sale.group_pos_user").id])],
            }
        )
        journal = cls.env["account.journal"].create(
            {"name": "Kiosk Close Z Http", "type": "sale", "code": "KCZHT", "company_id": company.id}
        )

        def _make_config(name, mode):
            config = cls.env["pos.config"].create(
                {
                    "name": name,
                    "journal_id": journal.id,
                    "invoice_journal_id": journal.id,
                    "self_ordering_mode": mode,
                    "self_ordering_default_user_id": pos_user.id,
                    "payment_method_ids": [(6, 0, [])],
                }
            )
            session = cls.env["pos.session"].create(
                {"config_id": config.id, "user_id": cls.env.ref("base.user_admin").id}
            )
            session.set_opening_control(0, "")
            return config

        cls.kiosk_config = _make_config("Kiosk Close Z Http Kiosk", "kiosk")
        cls.mobile_config = _make_config("Kiosk Close Z Http QR", "mobile")

    def _jsonrpc(self, route, **params):
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}),
            headers={"Content-Type": "application/json"},
        )
        return response.json() if response.content else {}

    def test_kiosk_token_reaches_the_route(self):
        """Control: con el token del Kiosko la ruta responde."""
        body = self._jsonrpc(
            "/l10n_ve_pos_mf_self_order/kiosk/close_session/check",
            access_token=self.kiosk_config.access_token,
        )
        self.assertNotIn("error", body)
        self.assertEqual(body["result"]["pending_orders"], [])

    def test_invalid_token_rejected(self):
        for route in ("close_session/check", "report_z", "close_session"):
            body = self._jsonrpc(
                f"/l10n_ve_pos_mf_self_order/kiosk/{route}",
                access_token="not-a-token",
                value={"valid": True, "data": {}},
            )
            self.assertIn("error", body, route)
            self.assertNotIn("result", body, route)

    def test_mobile_token_rejected(self):
        session = self.mobile_config.current_session_id
        for route in ("close_session/check", "report_z", "close_session"):
            body = self._jsonrpc(
                f"/l10n_ve_pos_mf_self_order/kiosk/{route}",
                access_token=self.mobile_config.access_token,
                value={
                    "valid": True,
                    "data": {"_registeredMachineNumber": SERIAL, "_dailyClosureCounter": 5},
                },
            )
            self.assertIn("error", body, route)
        self.assertEqual(session.state, "opened")
        self.assertFalse(session.report_z)
