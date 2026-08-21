"""Tests de la facturación DIFERIDA del Kiosko (resiliencia).

Spec: ``openspec/changes/l10n-ve-pos-self-order-kiosk-invoice-recovery``.

``pos.order._process_saved_order`` marca las órdenes del Kiosko con el contexto
``kiosk_defer_invoice`` para que ``_generate_pos_order_invoice`` aísle la
generación de la factura en un ``savepoint``: si falla, la orden queda ``paid`` +
``to_invoice`` SIN ``account_move`` (recuperable), en vez de perderse por el
rollback del request. La ruta EXPLÍCITA (sin el flag) sigue propagando el error.

Se fuerza el fallo parcheando el ``_create_invoice`` del core (equivale a un
diario/secuencia inválido): ``l10n_ve_pos_mf._generate_pos_order_invoice`` llama a
``super()``, así que la cadena llega al core y revienta ahí dentro.
"""

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

CORE = "odoo.addons.point_of_sale.models.pos_order.PosOrder"


def _boom(self, *args, **kwargs):
    raise UserError("factura inválida (forzado en test)")


@tagged("post_install", "-at_install", "l10n_ve_pos_self_order")
class TestKioskDeferredInvoicing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Kiosk Deferred Co",
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

        account = cls.env["account.account"].create(
            {
                "name": "Kiosk Deferred Income",
                "code": "400000KD",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        tax_group = cls.env["account.tax.group"].create(
            {"name": "Kiosk Deferred Tax Group", "company_id": cls.company.id}
        )
        tax = cls.env["account.tax"].create(
            {
                "name": "Kiosk Deferred Tax",
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
                "name": "Kiosk Deferred Category",
                "property_account_income_categ_id": account.id,
                "property_account_expense_categ_id": account.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Kiosk Deferred Product",
                # `service`: `_process_saved_order` llama a `_create_order_picking`
                # y un producto almacenable crearía un stock.move cuya ubicación
                # (Clientes) es de la compañía principal, chocando con la compañía
                # de test (`_check_company`). Un servicio no genera movimiento, así
                # que el flujo llega a la facturación (que es lo que probamos).
                "type": "service",
                "lst_price": 100.0,
                "available_in_pos": True,
                "company_id": cls.company.id,
                "categ_id": category.id,
            }
        )
        cls.product.with_company(cls.company).write(
            {"property_account_income_id": account.id}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Kiosk Deferred Partner", "prefix_vat": "V", "vat": "10101010"}
        )

        sale_journal = cls.env["account.journal"].create(
            {
                "name": "Kiosk Deferred Sale Journal",
                "type": "sale",
                "code": "KDSJ",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Kiosk Deferred Config",
                "company_id": cls.company.id,
                "currency_id": vef.id,
                "journal_id": sale_journal.id,
                "invoice_journal_id": sale_journal.id,
                "self_ordering_mode": "kiosk",
                "payment_method_ids": [(6, 0, [])],
            }
        )
        cls.session = cls.env["pos.session"].create(
            {"config_id": cls.config.id, "user_id": cls.env.ref("base.user_admin").id}
        )

    def _make_order(self):
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": self.session.id,
                "partner_id": self.partner.id,
                "state": "paid",
                "to_invoice": True,
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
            }
        )

    def test_deferred_failure_keeps_order_paid(self):
        """Con el flag kiosk_defer_invoice, un fallo de factura NO se propaga: la
        orden queda paid + to_invoice sin account_move; el savepoint revierte el
        estado 'done' que el core fija de primero."""
        order = self._make_order()
        with patch(f"{CORE}._create_invoice", _boom):
            result = order.with_context(
                kiosk_defer_invoice=True
            )._generate_pos_order_invoice()
        self.assertFalse(result, "debe devolver un account.move vacío")
        self.assertFalse(order.account_move, "no debe quedar factura colgada")
        self.assertEqual(order.state, "paid", "el savepoint revierte el 'done'")
        self.assertTrue(order.to_invoice, "sigue pendiente de facturar")

    def test_explicit_path_propagates_error(self):
        """Sin el flag (facturación explícita: panel de recuperación / backend),
        el error SÍ se propaga para que el operador vea la causa."""
        order = self._make_order()
        with patch(f"{CORE}._create_invoice", _boom):
            with self.assertRaises(UserError):
                order._generate_pos_order_invoice()

    def test_process_saved_order_sets_defer_flag_for_kiosk(self):
        """_process_saved_order enruta las órdenes del Kiosko por el diferido: un
        fallo de factura las conserva pagadas en vez de perderlas."""
        order = self._make_order()
        with patch(f"{CORE}._create_invoice", _boom):
            order._process_saved_order(draft=False)
        self.assertEqual(order.state, "paid")
        self.assertFalse(order.account_move)
        self.assertTrue(order.to_invoice)
