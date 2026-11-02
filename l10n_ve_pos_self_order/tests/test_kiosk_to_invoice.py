"""Tests for the Kiosk ``to_invoice`` forcing contract.

Spec: ``openspec/changes/l10n-ve-pos-self-order-kiosk-invoicing/specs/
pos-self-order-kiosk-invoicing/spec.md`` — "Toda orden del Kiosko se marca
para facturar".

``l10n_ve_pos`` requires every POS sale to emit a fiscal invoice (SENIAT) and
enforces it on the cashier with a JS patch scoped to the cashier asset bundle
(``point_of_sale._assets_pos``). The Kiosk/Self-Order app loads a different
bundle that never includes that patch, so the client sends no ``to_invoice``
and core ``_check_pos_order`` copies the missing value through. This module
overrides ``_check_pos_order`` to force ``to_invoice=True`` for Kiosk orders;
these tests exercise that override directly on the vals it builds.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestKioskToInvoice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test VE Kiosk Invoice Co",
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

        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk Invoice Sale Journal",
                "type": "sale",
                "code": "KISJ",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Kiosk Invoice Config",
                "company_id": cls.company.id,
                "currency_id": vef.id,
                "journal_id": cls.sale_journal.id,
                "self_ordering_mode": "kiosk",
                # invoice_journal_id has the SAME ambient-company default
                # pitfall as payment_method_ids below
                # (point_of_sale/models/pos_config.py:90-95) — left unset
                # it silently pulls in a journal from a DIFFERENT company
                # and _check_company() rejects the whole record.
                "invoice_journal_id": cls.sale_journal.id,
                # payment_method_ids' default is computed from
                # self.env.company (ambient), not from company_id above
                # (point_of_sale/models/pos_config.py:170) — left unset it
                # pulls in a payment method from a DIFFERENT company and
                # trips _check_company_payment. This file never takes a
                # payment, so an explicit empty list is enough.
                "payment_method_ids": [(6, 0, [])],
            }
        )

    def _order_payload(self, **overrides):
        """Minimal Kiosk order payload for ``_check_pos_order``. Mirrors what
        the Self-Order client sends: no partner/lines needed to prove the
        ``to_invoice`` forcing (that logic runs before line processing)."""
        payload = {
            "to_invoice": False,
            "lines": [],
            "amount_total": 0.0,
            "amount_tax": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
        }
        payload.update(overrides)
        return payload

    def _check(self, payload, device_type="kiosk"):
        return self.env["pos.order"]._check_pos_order(self.config, payload, device_type)

    # ------------------------------------------------------------------
    # Kiosko: se fuerza
    # ------------------------------------------------------------------
    def test_kiosk_forces_to_invoice_when_client_sends_false(self):
        """Scenario: El cliente del Kiosko envía to_invoice=False → se persiste
        con to_invoice=True."""
        vals = self._check(self._order_payload(to_invoice=False))
        self.assertTrue(
            vals["to_invoice"],
            "El Kiosko debe forzar to_invoice=True aunque el cliente mande False",
        )

    def test_kiosk_forces_to_invoice_when_client_omits_it(self):
        """Scenario: payload sin la clave to_invoice → igual se fuerza True."""
        payload = self._order_payload()
        del payload["to_invoice"]
        self.assertTrue(self._check(payload)["to_invoice"])

    def test_kiosk_keeps_to_invoice_true_when_client_already_sends_true(self):
        """No-regresión: si el cliente ya manda to_invoice=True, sigue True."""
        self.assertTrue(self._check(self._order_payload(to_invoice=True))["to_invoice"])

    # ------------------------------------------------------------------
    # Otros modos de self-order: NO se fuerza
    # ------------------------------------------------------------------
    def test_mobile_does_not_force_to_invoice(self):
        """Scenario: modo mobile (QR de mesa), sin partner garantizado → NO se
        fuerza to_invoice; se respeta el comportamiento nativo."""
        self.config.self_ordering_mode = "mobile"
        vals = self._check(self._order_payload(to_invoice=False), device_type="mobile")
        self.assertFalse(
            vals["to_invoice"], "El flujo mobile no debe forzarse a facturar"
        )

    def test_consultation_mode_does_not_force_to_invoice(self):
        """Modo consultation (solo menú QR): tampoco se fuerza."""
        self.config.self_ordering_mode = "consultation"
        vals = self._check(self._order_payload(to_invoice=False), device_type="mobile")
        self.assertFalse(vals["to_invoice"])

    def test_disabled_self_ordering_does_not_force_to_invoice(self):
        """Modo 'nothing' (self-order desactivado): no se toca to_invoice."""
        self.config.self_ordering_mode = "nothing"
        vals = self._check(self._order_payload(to_invoice=False))
        self.assertFalse(vals["to_invoice"])

    def test_non_kiosk_mode_respects_client_true(self):
        """En un modo no-kiosko, si el cliente manda True, se respeta True (no
        se pisa a False): el override solo AÑADE el forzado en kiosko, nunca
        desactiva la facturación pedida por el cliente."""
        self.config.self_ordering_mode = "mobile"
        vals = self._check(
            self._order_payload(to_invoice=True), device_type="mobile"
        )
        self.assertTrue(vals["to_invoice"])
