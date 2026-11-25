"""Precio alterno completado en el servidor para las líneas del PdV (#16676).

Desde el commit del core ``534aaac9114d``, ``pos_sale`` sobrescribe
``PosOrderline.setUnitPrice`` sin llamar a ``super`` cuando la línea tiene
``sale_order_line_id``: el patch de ``l10n_ve_pos`` (único que fija
``foreign_price`` en el frontend) queda saltado y la línea se sincroniza con
``foreign_price = 0``, que ``_get_invoice_lines_values`` copia a la factura.

``pos.order.line`` completa ahora ese valor en el servidor con la tasa del PdV
estampada en la orden (``pos.order.foreign_currency_rate``), nunca con la de la
orden de venta ni con la del día.
"""

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

# Tasa del PdV del fixture (main -> alterna).
POS_RATE = 36.5


class PosLineForeignPriceHelpers:
    """Helpers compartidos por las pruebas del precio alterno de líneas del PdV."""

    def _new_session(self):
        # Una sola sesión abierta por caja: se reutiliza si ya existe.
        session = self.env["pos.session"].search(
            [("config_id", "=", self.config.id), ("state", "!=", "closed")], limit=1
        )
        return session or self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    def _make_product(self, name, **extra):
        product = (
            self.env["product.product"]
            .with_company(self.company)
            .create(
                {
                    "name": name,
                    "type": "service",
                    "available_in_pos": True,
                    "company_id": self.company.id,
                    "categ_id": self.product_category.id,
                    "taxes_id": [Command.set(self.tax.ids)],
                    "supplier_taxes_id": [Command.set(self.tax.ids)],
                    **extra,
                }
            )
        )
        product.with_company(self.company).write(
            {"property_account_income_id": self.account_income.id}
        )
        return product

    def _sale_order(self, specs):
        """Orden de venta confirmada (con ``write``: confirmar falla en el
        fixture por rutas de stock). ``specs``: lista de ``(producto, precio,
        extra)``."""
        sale = (
            self.env["sale.order"]
            .with_company(self.company)
            .create(
                {
                    "partner_id": self.company.partner_id.id,
                    "company_id": self.company.id,
                    "order_line": [
                        Command.create(
                            {
                                "product_id": product.id,
                                "product_uom_qty": 1,
                                "price_unit": price,
                                **extra,
                            }
                        )
                        for product, price, extra in specs
                    ],
                }
            )
        )
        sale.write({"state": "sale"})
        return sale

    def _invoice_product_lines(self, invoice):
        return invoice.invoice_line_ids.filtered(lambda line: line.display_type == "product")

    def _order_header(self, session, *, rate=POS_RATE, name="OL/BF", **extra):
        vals = {
            "name": name,
            "company_id": self.company.id,
            "session_id": session.id,
            "partner_id": self.company.partner_id.id,
            "pricelist_id": self.company.partner_id.property_product_pricelist.id,
            "foreign_currency_rate": rate,
            "foreign_amount_total": 0.0,
            "amount_total": 0.0,
            "amount_tax": 0.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "last_order_preparation_change": "{}",
        }
        vals.update(extra)
        return self.env["pos.order"].create(vals)

    def _line_vals(self, order, *, price_unit=100.0, qty=1.0, foreign_price=0.0, **extra):
        subtotal = price_unit * qty
        vals = {
            "order_id": order.id,
            "name": "LINE",
            "product_id": self.product.id,
            "price_unit": price_unit,
            "qty": qty,
            "price_subtotal": subtotal,
            "price_subtotal_incl": subtotal * (1 + self.tax.amount / 100),
            "tax_ids": [Command.set(self.tax.ids)],
            "foreign_price": foreign_price,
        }
        vals.update(extra)
        return vals

    def _line(self, order, **kw):
        return self.env["pos.order.line"].create(self._line_vals(order, **kw))

    def _force_zero(self, line):
        """Deja ``foreign_price`` en 0 por SQL (dato anterior al cambio)."""
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_order_line SET foreign_price = 0 WHERE id = %s", (line.id,))
        line.invalidate_recordset(["foreign_price"])

    def _full_order(self, rate=POS_RATE, **line_kw):
        """Orden con una línea de 100 + IVA 16 sin alterno."""
        order = self._order_header(
            self._new_session(), rate=rate, amount_total=116.0, amount_tax=16.0
        )
        self._line(order, **line_kw)
        return order


    # --- sync_from_ui (patrón de test_pos_serialization) -----------------
    def _sync_payload(self, session, *, uuid, rate, lines, **extra):
        payload = {
            "id": False,
            "name": "Order/BF/%s" % uuid,
            "uuid": uuid,
            "access_token": "token-%s" % uuid,
            "session_id": session.id,
            "company_id": self.company.id,
            "config_id": self.config.id,
            "currency_id": self.foreign_currency.id,
            "pricelist_id": self.company.partner_id.property_product_pricelist.id,
            "partner_id": False,
            "date_order": False,
            "state": "draft",
            "amount_total": 116.0,
            "amount_tax": 16.0,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "foreign_amount_total": 0.0,
            "foreign_currency_rate": rate,
            "lines": lines,
            "payment_ids": [],
            "last_order_preparation_change": "{}",
        }
        payload.update(extra)
        return payload

    def _sync_line_vals(self, uuid, price_unit, foreign_price, **extra):
        vals = {
            "name": "SYNC",
            "uuid": uuid,
            "product_id": self.product.id,
            "price_unit": price_unit,
            "discount": 0.0,
            "qty": 1.0,
            "price_subtotal": price_unit,
            "price_subtotal_incl": price_unit * 1.16,
            "tax_ids": [(6, 0, self.tax.ids)],
            "foreign_price": foreign_price,
            "foreign_subtotal": 0.0,
            "foreign_total": 0.0,
        }
        vals.update(extra)
        return vals

    def _sync_twice(self, rate, first_price, second_price, second_foreign):
        """Sincroniza dos veces el mismo uuid: la segunda manda la línea como
        ``[1, id, vals]``. Devuelve la línea guardada."""
        session = self._new_session()
        uuid = "bf-%s-%s" % (id(self), self.env["pos.order"].search_count([]))
        first_vals = self._sync_line_vals("%s-l" % uuid, first_price, 0.0)
        self.env["pos.order"].sync_from_ui(
            [self._sync_payload(session, uuid=uuid, rate=rate, lines=[[0, 0, first_vals]])]
        )
        order = self.env["pos.order"].search([("uuid", "=", uuid)])
        self.assertEqual(len(order.lines), 1)
        line = order.lines
        second_vals = self._sync_line_vals("%s-l" % uuid, second_price, second_foreign)
        self.env["pos.order"].sync_from_ui(
            [self._sync_payload(session, uuid=uuid, rate=rate, lines=[[1, line.id, second_vals]])]
        )
        line.invalidate_recordset()
        return line


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_line_foreign_backfill")
class TestPosLineForeignPriceBackfill(PosLineForeignPriceHelpers, TestPosSessionAccountingBase):
    # ------------------------------------------------------------------
    # 1.5 a-f: el servidor completa el alterno
    # ------------------------------------------------------------------
    def test_a_sale_line_without_foreign_price_is_filled(self):
        line = self._line(self._order_header(self._new_session()), price_unit=100.0)
        self.assertAlmostEqual(line.foreign_price, 100.0 * POS_RATE)

    def test_b_negative_price_keeps_sign(self):
        line = self._line(self._order_header(self._new_session()), price_unit=-15.0)
        self.assertAlmostEqual(line.foreign_price, -15.0 * POS_RATE)

    def test_c_foreign_product_price_precision(self):
        self.env.ref("l10n_ve_accountant.alternative_price_product").digits = 2
        line = self._line(self._order_header(self._new_session()), price_unit=1.2345)
        self.assertEqual(line.foreign_price, 45.06)

    def test_d_cashier_in_foreign_currency_uses_unit_price(self):
        # El fixture opera en la moneda alterna (diario en VEF): el PdV estampa
        # tasa 1 y, si faltara la tasa, se usa el precio unitario.
        order = self._order_header(self._new_session(), rate=1.0)
        self.assertEqual(order.currency_id, self.foreign_currency)
        self.assertEqual(self._line(order, price_unit=1.2345).foreign_price, 1.2345)
        order.foreign_currency_rate = 0.0
        self.assertEqual(self._line(order, price_unit=7.0).foreign_price, 7.0)

    def test_e_present_price_is_kept_zero_price_or_no_rate_stays_zero(self):
        session = self._new_session()
        order = self._order_header(session)
        self.assertEqual(self._line(order, foreign_price=3600.0).foreign_price, 3600.0)
        self.assertEqual(self._line(order, price_unit=0.0).foreign_price, 0.0)
        # Caja que no es alterna y orden sin tasa: queda como llegó.
        self.config.currency_id = self.company.currency_id
        no_rate = self._order_header(session, rate=0.0, name="OL/BF-NR")
        self.assertNotEqual(no_rate.currency_id, self.foreign_currency)
        self.assertEqual(self._line(no_rate).foreign_price, 0.0)

    def test_f_refund_copies_original_or_uses_original_rate(self):
        session = self._new_session()
        sale = self._line(self._order_header(session), foreign_price=3.45)
        refund_order = self._order_header(session, rate=40.0, name="OL/BF-R")
        refund = self._line(
            refund_order, qty=-1.0, refunded_orderline_id=sale.id
        )
        # Copia la del original aunque precio x tasa dé otro valor.
        self.assertEqual(refund.foreign_price, 3.45)

        # Original en 0 (dato dañado): tasa de la venta original (36.5), no 40.
        self._force_zero(sale)
        refund2 = self._line(refund_order, qty=-1.0, refunded_orderline_id=sale.id)
        self.assertAlmostEqual(refund2.foreign_price, 100.0 * POS_RATE)

    def test_pos_rate_stamped_in_order_wins_over_rate_of_day(self):
        """La tasa es la del PdV estampada en la orden, no la del día (la de la
        sale.order la cubre ``test_settled_sale_order_lines_and_invoice``)."""
        self._create_rate_of_day(40.0)
        line = self._line(self._order_header(self._new_session(), rate=POS_RATE))
        self.assertAlmostEqual(line.foreign_price, 100.0 * POS_RATE)

    # ------------------------------------------------------------------
    # 1.5 g: write (reglas A y B)
    # ------------------------------------------------------------------
    def test_g_write_rules(self):
        line = self._line(self._order_header(self._new_session()))
        self.assertAlmostEqual(line.foreign_price, 3650.0)

        # Regla A: llega con alterno 0 y mismo precio.
        line.write({"price_unit": 100.0, "foreign_price": 0.0})
        self.assertAlmostEqual(line.foreign_price, 3650.0)

        # Regla B: cambia el precio con el alterno anterior.
        line.write({"price_unit": 120.0, "foreign_price": 3650.0})
        self.assertAlmostEqual(line.foreign_price, 4380.0)
        line.write({"price_unit": 130.0})
        self.assertAlmostEqual(line.foreign_price, 4745.0)

        # Cambio de precio con su alterno nuevo: se respeta.
        line.write({"price_unit": 120.0, "foreign_price": 4400.0})
        self.assertEqual(line.foreign_price, 4400.0)

    def test_h_rounded_to_zero_is_valid(self):
        self.env.ref("l10n_ve_accountant.alternative_price_product").digits = 2
        order = self._order_header(self._new_session(), rate=1 / 600)
        line = self._line(order, price_unit=2.0)  # 0,0033 -> 0,00
        self.assertEqual(line.foreign_price, 0.0)
        line.write({"price_unit": 600.0, "foreign_price": 0.0})
        self.assertEqual(line.foreign_price, 1.0)
        line.write({"price_unit": 2.0})  # regla B hacia 0
        self.assertEqual(line.foreign_price, 0.0)
        # Ni la factura ni otra escritura reentran.
        line.write({"price_unit": 2.0, "foreign_price": 0.0})
        self.assertEqual(line.foreign_price, 0.0)

    def test_new_line_in_refund_order_uses_order_rate(self):
        """Una línea nueva de una orden de reembolso (cambio de producto) usa la
        tasa de su orden; solo la que reembolsa otra usa la de la original."""
        session = self._new_session()
        sale = self._line(self._order_header(session), foreign_price=3650.0)
        refund_order = self._order_header(session, rate=40.0, name="OL/BF-RX", is_refund=True)
        self._line(refund_order, qty=-1.0, refunded_orderline_id=sale.id)
        new_line = self._line(refund_order, price_unit=100.0)
        self.assertAlmostEqual(new_line.foreign_price, 100.0 * 40.0)

    def test_g_sync_from_ui_twice(self):
        # Con foreign_price 0 en ambos syncs sigue en 3.650.
        line = self._sync_twice(POS_RATE, 100.0, 100.0, 0.0)
        self.assertAlmostEqual(line.foreign_price, 3650.0)
        # Precio 120 con el alterno viejo 3.650 -> 4.380 (regla B).
        line = self._sync_twice(POS_RATE, 100.0, 120.0, 3650.0)
        self.assertAlmostEqual(line.foreign_price, 4380.0)

    def test_g_sync_from_ui_respects_new_foreign_price(self):
        line = self._sync_twice(POS_RATE, 100.0, 120.0, 4400.0)
        self.assertEqual(line.foreign_price, 4400.0)

    def test_sync_from_ui_rounded_to_zero(self):
        self.env.ref("l10n_ve_accountant.alternative_price_product").digits = 2
        line = self._sync_twice(1 / 600, 2.0, 2.0, 0.0)
        self.assertEqual(line.foreign_price, 0.0)
        line = self._sync_twice(1 / 600, 600.0, 900.0, 1.0)
        self.assertEqual(line.foreign_price, 1.5)

    # ------------------------------------------------------------------
    # Configuración real de Venezuela: multiplicador 1/600 y precisión
    # "Foreign Product Price" = 2 (los precios del fixture se leen como Bs).
    # ------------------------------------------------------------------
    def _ve_config(self):
        self.env.ref("l10n_ve_accountant.alternative_price_product").digits = 2
        return 1 / 600

    def test_ve_a_normal_price(self):
        rate = self._ve_config()
        line = self._line(self._order_header(self._new_session(), rate=rate), price_unit=600.0)
        self.assertEqual(line.foreign_price, 1.0)

    def test_ve_b_negative_price(self):
        rate = self._ve_config()
        line = self._line(self._order_header(self._new_session(), rate=rate), price_unit=-1200.0)
        self.assertEqual(line.foreign_price, -2.0)

    def test_ve_g_sync_twice(self):
        rate = self._ve_config()
        line = self._sync_twice(rate, 600.0, 600.0, 0.0)
        self.assertEqual(line.foreign_price, 1.0)
        line = self._sync_twice(rate, 600.0, 900.0, 1.0)
        self.assertEqual(line.foreign_price, 1.5)
        line = self._sync_twice(rate, 600.0, 900.0, 1.6)
        self.assertEqual(line.foreign_price, 1.6)

    # ------------------------------------------------------------------
    # 2.2: red de seguridad en la factura
    # ------------------------------------------------------------------
    def _assert_invoice(self, invoice, order):
        # ``foreign_credit`` no se asevera: en este fixture el diario de la
        # factura está en la moneda alterna y l10n_ve_accountant deriva
        # débito/crédito alterno del importe en moneda de la factura.
        product_lines = invoice.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertTrue(product_lines)
        for line in product_lines:
            self.assertAlmostEqual(line.foreign_price, 3650.0)
            self.assertAlmostEqual(line.foreign_subtotal, 3650.0)

    def test_invoice_lines_created_without_foreign_price(self):
        self._create_rate_of_day(40.0)
        order = self._full_order()
        invoice = order._create_invoice(order._prepare_invoice_vals())
        self._assert_invoice(invoice, order)
        tax_line = invoice.line_ids.filtered(lambda l: l.display_type == "tax")
        self.assertAlmostEqual(sum(tax_line.mapped("foreign_credit")), 584.0)

    def test_invoice_safety_net_for_legacy_zero_line(self):
        self._create_rate_of_day(40.0)
        order = self._full_order()
        self._force_zero(order.lines)
        invoice = order._create_invoice(order._prepare_invoice_vals())
        self._assert_invoice(invoice, order)
        self.assertEqual(order.lines.foreign_price, 0.0)

    def test_settled_sale_order_lines_and_invoice(self):
        """Caso ``pos_sale``: líneas ligadas a una orden de venta (#16676)."""
        if "sale_order_line_id" not in self.env["pos.order.line"]._fields:
            self.skipTest("pos_sale no está instalado")
        # Orden de venta con tasa propia distinta a la del PdV.
        self._create_rate_of_day(40.0)
        partner = self.company.partner_id
        sale_line_vals = {
            "product_id": self.product.id,
            "product_uom_qty": 1,
            "price_unit": 100.0,
        }
        sale = self.env["sale.order"].with_company(self.company).create(
            {
                "partner_id": partner.id,
                "company_id": self.company.id,
                "order_line": [
                    Command.create(sale_line_vals),
                    Command.create(sale_line_vals),
                ],
            }
        )
        # Sin pasar por logística: la prueba es del precio alterno del PdV.
        sale.write({"state": "sale"})
        order = self._order_header(
            self._new_session(),
            amount_total=232.0,
            amount_tax=32.0,
        )
        for sol in sale.order_line:
            self._line(
                order,
                sale_order_origin_id=sale.id,
                sale_order_line_id=sol.id,
                foreign_price=0.0,
            )
        for line in order.lines:
            self.assertAlmostEqual(line.foreign_price, 100.0 * POS_RATE)
        invoice = order._create_invoice(order._prepare_invoice_vals())
        product_lines = invoice.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(len(product_lines), 2)
        for line in product_lines:
            self.assertAlmostEqual(line.foreign_price, 100.0 * POS_RATE)

