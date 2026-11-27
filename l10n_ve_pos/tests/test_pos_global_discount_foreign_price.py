"""Precio foráneo de las líneas del descuento global (ticket 16547).

En el PdV, ``pos_discount`` crea las líneas [DISC] con precio negativo y, cada
vez que cambia la orden, les reasigna ``price_unit`` directo, sin pasar por el
``setUnitPrice`` de ``l10n_ve_pos``. Las líneas llegaban con
``foreign_price = 0`` (o con el de un monto anterior) y la factura, que copia
``foreign_price`` a la línea contable, quedaba con el alterno sin descontar.

``pos.order.line`` fija ahora ``foreign_price`` de esas líneas a la tasa de la
orden (en un reembolso, a la de la venta original) al crearlas y cada vez que
cambia su precio.
"""

from unittest import SkipTest

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

# Tasa de la venta del fixture: la compañía en USD y la alterna en VEF, así
# que el multiplicador main → foreign es 36.5.
SALE_RATE = 36.5


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_global_discount_foreign")
class TestPosGlobalDiscountForeignPrice(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "discount_product_id" not in cls.env["pos.config"]._fields:
            raise SkipTest("pos_discount no está instalado")
        cls.discount_product = (
            cls.env["product.product"]
            .with_company(cls.company)
            .create(
                {
                    "name": "Descuento global",
                    "type": "service",
                    "available_in_pos": True,
                    "company_id": cls.company.id,
                    "categ_id": cls.product_category.id,
                    "taxes_id": [Command.set(cls.tax.ids)],
                    "supplier_taxes_id": [Command.set(cls.tax.ids)],
                }
            )
        )
        cls.discount_product.with_company(cls.company).write(
            {"property_account_income_id": cls.account_income.id}
        )
        cls.config.write(
            {"module_pos_discount": True, "discount_product_id": cls.discount_product.id}
        )

    def _new_session(self):
        return self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    def _order(self, session, lines, *, rate=SALE_RATE, name="OL/DISC", is_refund=False):
        amount_untaxed = sum(vals["price_unit"] * vals.get("qty", 1.0) for vals in lines)
        amount_tax = round(amount_untaxed * self.tax.amount / 100, 2)
        return self.env["pos.order"].create(
            {
                "name": name,
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_currency_rate": rate,
                "is_refund": is_refund,
                "foreign_amount_total": 0.0,
                "amount_total": amount_untaxed + amount_tax,
                "amount_tax": amount_tax,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
                "lines": [Command.create(self._line_vals(**vals)) for vals in lines],
            }
        )

    def _line_vals(self, product, price_unit, qty=1.0, foreign_price=0.0, refunded=None):
        subtotal = price_unit * qty
        vals = {
            "name": product.name,
            "product_id": product.id,
            "price_unit": price_unit,
            "qty": qty,
            "price_subtotal": subtotal,
            "price_subtotal_incl": subtotal * (1 + self.tax.amount / 100),
            "tax_ids": [Command.set(self.tax.ids)],
            "foreign_price": foreign_price,
        }
        if refunded:
            vals["refunded_orderline_id"] = refunded.id
        return vals

    def _sale(self, price_unit=100.0, **kw):
        return {"product": self.product, "price_unit": price_unit,
                "foreign_price": price_unit * SALE_RATE, **kw}

    def _discount(self, price_unit=-15.0, **kw):
        return {"product": self.discount_product, "price_unit": price_unit, **kw}

    def _discount_line(self, order):
        return order.lines.filtered(lambda line: line.product_id == self.discount_product)

    def test_discount_line_gets_foreign_price_at_order_rate(self):
        order = self._order(self._new_session(), [self._sale(), self._discount()])

        # Llega con foreign_price 0 (el PdV no lo calculaba) y queda a la tasa
        # de la orden, con el signo del descuento.
        self.assertAlmostEqual(self._discount_line(order).foreign_price, -15.0 * SALE_RATE)

    def test_other_lines_keep_their_foreign_price(self):
        order = self._order(self._new_session(), [self._sale(foreign_price=3600.0), self._discount()])

        # Solo se tocan las líneas del producto de descuento: la de venta
        # conserva el precio foráneo que mandó el PdV.
        sale_line = order.lines - self._discount_line(order)
        self.assertEqual(sale_line.foreign_price, 3600.0)

    def test_stale_foreign_price_is_recomputed_when_price_changes(self):
        order = self._order(self._new_session(), [self._sale(), self._discount()])
        discount_line = self._discount_line(order)

        # pos_discount reasigna price_unit al cambiar la orden; el foreign_price
        # que viaja con la línea es el del monto anterior.
        discount_line.write({"price_unit": -20.0, "foreign_price": -15.0 * SALE_RATE})
        self.assertAlmostEqual(discount_line.foreign_price, -20.0 * SALE_RATE)

        # Un foreign_price desfasado sin cambio de precio también se corrige.
        discount_line.write({"foreign_price": 1.0})
        self.assertAlmostEqual(discount_line.foreign_price, -20.0 * SALE_RATE)

    def test_without_discount_product_line_is_untouched(self):
        self.config.discount_product_id = False
        order = self._order(self._new_session(), [self._sale(), self._discount(foreign_price=-5.0)])

        # Sin producto de descuento configurado la línea es una más.
        self.assertEqual(self._discount_line(order).foreign_price, -5.0)

    def test_refund_discount_line_uses_original_sale_rate(self):
        session = self._new_session()
        sale = self._order(session, [self._sale(), self._discount()], name="OL/DISC-V")
        sale_line = sale.lines - self._discount_line(sale)

        # El reembolso se hace a otra tasa, pero pos_discount vuelve a aplicar
        # el descuento en la orden de reembolso con una línea nueva, sin
        # refunded_orderline_id. Debe revertir el USD de la venta: tasa original.
        refund = self._order(
            session,
            [
                {"product": self.product, "price_unit": 100.0, "qty": -1.0,
                 "foreign_price": sale_line.foreign_price, "refunded": sale_line},
                self._discount(price_unit=15.0),
            ],
            rate=40.0,
            name="OL/DISC-R",
            is_refund=True,
        )

        self.assertAlmostEqual(self._discount_line(refund).foreign_price, 15.0 * SALE_RATE)

    def test_invoice_alternate_total_is_discounted(self):
        # Tasa del día distinta a la de la venta: la factura debe quedar a la
        # de la orden.
        self._create_rate_of_day(40.0)
        order = self._order(self._new_session(), [self._sale(), self._discount()])

        invoice = order._create_invoice(order._prepare_invoice_vals())

        # La línea de descuento lleva su precio alterno a la factura, y la base
        # alterna queda descontada: (100 - 15) a la tasa de la orden, no 100.
        discount_invoice_line = invoice.invoice_line_ids.filtered(
            lambda line: line.product_id == self.discount_product
        )
        self.assertAlmostEqual(discount_invoice_line.foreign_price, -15.0 * SALE_RATE)
        self.assertAlmostEqual(
            sum(invoice.invoice_line_ids.mapped("foreign_subtotal")), 85.0 * SALE_RATE
        )
