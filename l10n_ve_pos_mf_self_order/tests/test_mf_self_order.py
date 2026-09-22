"""Tests Python de ``l10n_ve_pos_mf_self_order`` (módulo auto_install).

Cubre las dos costuras del modelo que el Kiosko fiscal necesita:

* ``_send_payment_result`` — el core NO incluye los pagos en el evento del bus
  ``PAYMENT_STATUS``; este módulo lo reemplaza para añadir ``pos.payment`` (la
  impresión fiscal en ``confirmationPage`` necesita el método de pago para leer
  su ``code_fiscal_printer``).
* ``_load_pos_self_data_fields`` — expone ``mf_invoice_number``/
  ``fiscal_machine``/``mf_reportz`` al esquema del cliente del Kiosko para que el
  número devuelto por la máquina viaje al servidor con la orden.
"""

from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase, tagged

@tagged("post_install", "-at_install", "l10n_ve_pos_mf_self_order")
class TestMfSelfOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usd = cls.env.ref("base.USD")
        cls.company = cls.env["res.company"].create(
            {
                "name": "MF SelfOrder Co",
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
                "name": "MF SelfOrder Income",
                "code": "400000MFS",
                "account_type": "income",
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )
        tax_group = cls.env["account.tax.group"].create(
            {"name": "MF SelfOrder Tax Group", "company_id": cls.company.id}
        )
        tax = cls.env["account.tax"].create(
            {
                "name": "MF SelfOrder Tax",
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
                "name": "MF SelfOrder Category",
                "property_account_income_categ_id": account.id,
                "property_account_expense_categ_id": account.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "MF SelfOrder Product",
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
            {"name": "MF SelfOrder Partner", "prefix_vat": "V", "vat": "20202020"}
        )

        sale_journal = cls.env["account.journal"].create(
            {
                "name": "MF SelfOrder Sale Journal",
                "type": "sale",
                "code": "MFSSJ",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        cash_journal = cls.env["account.journal"].create(
            {
                "name": "MF SelfOrder Cash Journal",
                "type": "cash",
                "code": "MFSCJ",
                "company_id": cls.company.id,
                "currency_id": vef.id,
            }
        )
        cls.cash_method = cls.env["pos.payment.method"].create(
            {
                "name": "MF SelfOrder Cash",
                "is_cash_count": True,
                "company_id": cls.company.id,
                "journal_id": cash_journal.id,
            }
        )
        # No se fuerza modo kiosko: `_send_payment_result` y
        # `_load_pos_self_data_fields` no dependen del modo, y así el método de
        # pago en efectivo es válido (el kiosko lo prohíbe).
        cls.config = cls.env["pos.config"].create(
            {
                "name": "MF SelfOrder Config",
                "company_id": cls.company.id,
                "currency_id": vef.id,
                "journal_id": sale_journal.id,
                "invoice_journal_id": sale_journal.id,
                "payment_method_ids": [(6, 0, [cls.cash_method.id])],
            }
        )
        cls.session = cls.env["pos.session"].create(
            {"config_id": cls.config.id, "user_id": cls.env.ref("base.user_admin").id}
        )

    def _make_paid_order_with_payment(self):
        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": self.session.id,
                "partner_id": self.partner.id,
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
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": self.cash_method.id,
                "amount": 100.0,
            }
        )
        return order

    def test_load_pos_self_data_fields_exposes_fiscal_fields(self):
        fields_list = self.env["pos.order"]._load_pos_self_data_fields(self.config)
        for field_name in ("mf_invoice_number", "fiscal_machine", "mf_reportz"):
            self.assertIn(field_name, fields_list)

    def test_send_payment_result_includes_pos_payment(self):
        """El evento del bus PAYMENT_STATUS debe incluir pos.payment (el core no
        lo hace), para que el cliente del Kiosko tenga el método de pago al
        imprimir la factura fiscal."""
        order = self._make_paid_order_with_payment()
        captured = {}

        def _capture(self_config, event, data, *args, **kwargs):
            captured["event"] = event
            captured["data"] = data

        # `_notify` se resuelve por MRO en la clase dinámica de pos.config (no
        # está en la clase core), así que se parchea sobre `type(self.config)`.
        # Se usa un resultado != "Success" para no disparar los envíos de
        # recibo/orden del core; el payload del bus se emite igual.
        with patch.object(type(self.config), "_notify", _capture):
            order._send_payment_result("Pending")

        self.assertEqual(captured.get("event"), "PAYMENT_STATUS")
        payload = captured["data"]["data"]
        self.assertIn("pos.payment", payload)
        self.assertTrue(payload["pos.payment"], "los pagos deben viajar en el bus")
        self.assertEqual(payload["pos.payment"][0]["amount"], 100.0)
