"""Tests de las rutas públicas del Kiosko (endurecimiento — revisión PR #1161).

Spec: ``openspec/changes/l10n-ve-pos-self-order-kiosk-review-hardening/specs/
pos-self-order-kiosk-endpoint-security/spec.md``.

Dos bloques:

* ``TestKioskIdentifyHelpers`` — unit tests de las funciones PURAS del
  controlador (validación de formato y rate-limit), sin HTTP.
* ``TestKioskPublicRoutes`` — ``HttpCase`` que ejerce las rutas públicas
  reales (``identify``/``identify_create``/``set_phone``/``session_orders``/
  ``create_invoice`` y la fiscal ``write_mf_invoice_data``): que ``identify`` no
  devuelva teléfono, dedup + fill-only, formato inválido rechazado, tope de
  ``limit``, pertenencia a la caja y guard de no-sobrescritura del número fiscal.
"""

import json

from odoo import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.l10n_ve_pos_self_order.controllers.orders import (
    _ve_vat_format_error,
    _ve_within_rate_limit,
    _RATE_LIMIT_MAX,
)


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestKioskIdentifyHelpers(TransactionCase):
    """Funciones puras del controlador (sin request HTTP)."""

    def test_vat_format_numeric_prefixes(self):
        """V/E/J/G exigen solo dígitos; letras → mensaje de error."""
        for prefix in ("V", "E", "J", "G"):
            self.assertIsNone(_ve_vat_format_error(prefix, "12345678"))
            self.assertTrue(_ve_vat_format_error(prefix, "12A45"))

    def test_vat_format_empty_is_rejected(self):
        self.assertTrue(_ve_vat_format_error("V", ""))
        self.assertTrue(_ve_vat_format_error("V", "   "))

    def test_vat_format_passport_is_free(self):
        """P (pasaporte) y C admiten alfanumérico (no numérico estricto)."""
        self.assertIsNone(_ve_vat_format_error("P", "AB123456"))
        self.assertIsNone(_ve_vat_format_error("C", "X-99"))

    def test_rate_limit_blocks_after_max_in_window(self):
        """Dentro de la ventana, la petición nº (MAX+1) para el MISMO token se
        frena; un token distinto no se ve afectado."""
        token = "unit-test-token-A"
        for _i in range(_RATE_LIMIT_MAX):
            self.assertTrue(_ve_within_rate_limit(token))
        # La siguiente supera el tope.
        self.assertFalse(_ve_within_rate_limit(token))
        # Otro token arranca su propia ventana.
        self.assertTrue(_ve_within_rate_limit("unit-test-token-B"))


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestKioskPublicRoutes(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Kiosk Routes Co",
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
        cls.company.write({"foreign_currency_id": vef.id})

        account = cls.env["account.account"].create(
            {
                "name": "Kiosk Routes Income",
                "code": "400000KR",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        tax_group = cls.env["account.tax.group"].create(
            {"name": "Kiosk Routes Tax Group", "company_id": cls.company.id}
        )
        tax = cls.env["account.tax"].create(
            {
                "name": "Kiosk Routes Tax",
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
                "name": "Kiosk Routes Category",
                "property_account_income_categ_id": account.id,
                "property_account_expense_categ_id": account.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Kiosk Routes Product",
                "lst_price": 100.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": category.id,
            }
        )
        cls.product.with_company(cls.company).write(
            {"property_account_income_id": account.id}
        )

        sale_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk Routes Sale Journal",
                "type": "sale",
                "code": "KRSJ",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        cash_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk Routes Cash Journal",
                "type": "cash",
                "code": "KRCJ",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        cash_method = cls.env["pos.payment.method"].create(
            {
                "name": "Kiosk Routes Cash",
                "is_cash_count": True,
                "company_id": cls.company.id,
                "journal_id": cash_journal.id,
            }
        )
        admin = cls.env.ref("base.user_admin")

        def _make_config(name):
            config = cls.env["pos.config"].create(
                {
                    "name": name,
                    "company_id": cls.company.id,
                    "currency_id": vef.id,
                    "journal_id": sale_journal.id,
                    "invoice_journal_id": sale_journal.id,
                    "self_ordering_mode": "kiosk",
                    "self_ordering_default_user_id": admin.id,
                    "payment_method_ids": [(6, 0, [cash_method.id])],
                }
            )
            # Sesión abierta (estado != closed) → has_active_session True, que es
            # lo que exige _verify_pos_config.
            cls.env["pos.session"].create(
                {"config_id": config.id, "user_id": admin.id}
            )
            return config

        cls.config = _make_config("Kiosk Routes Config A")
        cls.other_config = _make_config("Kiosk Routes Config B")

    # -- helpers -------------------------------------------------------------

    def _rpc(self, route, params):
        """Invoca una ruta jsonrpc pública y devuelve el ``result``."""
        response = self.url_open(
            route,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("error", payload, payload.get("error"))
        return payload["result"]

    def _make_partner(self, prefix_vat, vat, **vals):
        return self.env["res.partner"].create(
            {"name": f"Cliente {vat}", "prefix_vat": prefix_vat, "vat": vat, **vals}
        )

    def _make_paid_order(self, config, **vals):
        session = config.current_session_id
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "state": "paid",
                "amount_total": 100.0,
                "amount_tax": 0.0,
                "amount_paid": 100.0,
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

    # -- identify ------------------------------------------------------------

    def test_identify_not_found_returns_empty(self):
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify",
            {"access_token": self.config.access_token, "prefix_vat": "V", "vat": "99887766"},
        )
        self.assertEqual(result["res.partner"], [])
        self.assertFalse(result["has_phone"])

    def test_identify_found_never_returns_phone(self):
        """Aunque el partner tenga teléfono, la ruta NO lo devuelve; solo el
        flag has_phone."""
        self._make_partner("V", "11111111", phone="0412-0000000")
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify",
            {"access_token": self.config.access_token, "prefix_vat": "V", "vat": "11111111"},
        )
        partner = result["res.partner"][0]
        self.assertNotIn("phone", partner)
        self.assertTrue(result["has_phone"])
        self.assertEqual(partner["vat"], "11111111")

    def test_identify_found_without_phone_flags_missing(self):
        self._make_partner("V", "22222222")
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify",
            {"access_token": self.config.access_token, "prefix_vat": "V", "vat": "22222222"},
        )
        self.assertTrue(result["res.partner"])
        self.assertFalse(result["has_phone"])

    # -- identify_create -----------------------------------------------------

    def test_identify_create_dedup_does_not_duplicate(self):
        self._make_partner("V", "33333333")
        before = self.env["res.partner"].search_count(
            [("prefix_vat", "=", "V"), ("vat", "=", "33333333")]
        )
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify/create",
            {
                "access_token": self.config.access_token,
                "prefix_vat": "V",
                "vat": "33333333",
                "name": "Otro Nombre",
                "phone": "0412-1111111",
            },
        )
        after = self.env["res.partner"].search_count(
            [("prefix_vat", "=", "V"), ("vat", "=", "33333333")]
        )
        self.assertEqual(after, before, "no debe crear un duplicado")
        self.assertTrue(result["res.partner"])

    def test_identify_create_fill_only_phone(self):
        """El existente sin teléfono se rellena; con teléfono NO se sobrescribe."""
        p_empty = self._make_partner("V", "44444444")
        self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify/create",
            {
                "access_token": self.config.access_token,
                "prefix_vat": "V",
                "vat": "44444444",
                "name": "x",
                "phone": "0412-2222222",
            },
        )
        self.assertEqual(p_empty.phone, "0412-2222222")

        p_full = self._make_partner("V", "55555555", phone="0412-ORIGINAL")
        self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify/create",
            {
                "access_token": self.config.access_token,
                "prefix_vat": "V",
                "vat": "55555555",
                "name": "x",
                "phone": "0412-NUEVO",
            },
        )
        self.assertEqual(p_full.phone, "0412-ORIGINAL", "no debe sobrescribir")

    def test_identify_create_invalid_format_rejected(self):
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify/create",
            {
                "access_token": self.config.access_token,
                "prefix_vat": "V",
                "vat": "12AB34",
                "name": "x",
                "phone": "",
            },
        )
        self.assertEqual(result["res.partner"], [])
        self.assertTrue(result["error"])

    # -- set_phone -----------------------------------------------------------

    def test_set_phone_fill_only(self):
        p_empty = self._make_partner("V", "66666666")
        self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify/set_phone",
            {
                "access_token": self.config.access_token,
                "prefix_vat": "V",
                "vat": "66666666",
                "phone": "0412-3333333",
            },
        )
        self.assertEqual(p_empty.phone, "0412-3333333")

        p_full = self._make_partner("V", "77777777", phone="0412-KEEP")
        self._rpc(
            "/l10n_ve_pos_self_order/kiosk/identify/set_phone",
            {
                "access_token": self.config.access_token,
                "prefix_vat": "V",
                "vat": "77777777",
                "phone": "0412-OTRO",
            },
        )
        self.assertEqual(p_full.phone, "0412-KEEP")

    # -- session_orders ------------------------------------------------------

    def test_session_orders_caps_limit(self):
        """Un limit enorme queda acotado al tope duro (200)."""
        self._make_paid_order(self.config)
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/session_orders",
            {"access_token": self.config.access_token, "limit": 10**9},
        )
        self.assertLessEqual(len(result.get("pos.order", [])), 200)

    def test_session_orders_scoped_to_box(self):
        """Solo las órdenes de ESTA caja."""
        mine = self._make_paid_order(self.config)
        other = self._make_paid_order(self.other_config)
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/session_orders",
            {"access_token": self.config.access_token},
        )
        ids = {o["id"] for o in result.get("pos.order", [])}
        self.assertIn(mine.id, ids)
        self.assertNotIn(other.id, ids)

    # -- create_invoice ------------------------------------------------------

    def test_create_invoice_other_box_rejected(self):
        """Orden de OTRA caja → rechazada por la ruta de esta caja."""
        foreign = self._make_paid_order(self.other_config)
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/create_invoice",
            {"access_token": self.config.access_token, "order_id": foreign.id},
        )
        self.assertFalse(result["success"])

    def test_create_invoice_missing_order_rejected(self):
        result = self._rpc(
            "/l10n_ve_pos_self_order/kiosk/create_invoice",
            {"access_token": self.config.access_token, "order_id": 999999999},
        )
        self.assertFalse(result["success"])

    # -- write_mf_invoice_data (módulo fiscal, si está instalado) ------------

    def test_write_mf_no_overwrite_different_number(self):
        if "mf_invoice_number" not in self.env["pos.order"]._fields:
            self.skipTest("l10n_ve_pos_mf(_self_order) no instalado")
        order = self._make_paid_order(self.config)
        order.sudo().write({"mf_invoice_number": "00-000123"})
        result = self._rpc(
            "/l10n_ve_pos_mf_self_order/kiosk/write_mf_invoice_data",
            {
                "access_token": self.config.access_token,
                "order_id": order.id,
                "mf_invoice_number": "00-999999",
                "fiscal_machine": "TFHKA",
            },
        )
        self.assertFalse(result["success"], "no debe sobrescribir un número distinto")
        self.assertEqual(order.mf_invoice_number, "00-000123")

    def test_write_mf_other_box_rejected(self):
        if "mf_invoice_number" not in self.env["pos.order"]._fields:
            self.skipTest("l10n_ve_pos_mf(_self_order) no instalado")
        foreign = self._make_paid_order(self.other_config)
        result = self._rpc(
            "/l10n_ve_pos_mf_self_order/kiosk/write_mf_invoice_data",
            {
                "access_token": self.config.access_token,
                "order_id": foreign.id,
                "mf_invoice_number": "00-123456",
                "fiscal_machine": "TFHKA",
            },
        )
        self.assertFalse(result["success"])
