"""Escenarios de ``pos_sale`` para el precio alterno de las líneas del PdV (#16676).

Ninguna prueba ejecuta el JS del PdV: simulan el payload que llega con
``foreign_price`` 0 (anticipos, líneas partidas, combos, reembolsos) y verifican
que el servidor lo completa a la tasa del PdV estampada en la orden y que la
factura lo lleva. Los casos de ``pos_sale`` se saltan si no está instalado.
"""

from odoo import Command, fields
from odoo.tests import tagged

from .test_pos_line_foreign_price_backfill import POS_RATE, PosLineForeignPriceHelpers
from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_line_foreign_backfill")
class TestPosSaleForeignPriceScenarios(PosLineForeignPriceHelpers, TestPosSessionAccountingBase):
    def setUp(self):
        super().setUp()
        if "sale_order_line_id" not in self.env["pos.order.line"]._fields:
            self.skipTest("pos_sale no está instalado")
        self._create_rate_of_day(40.0)  # distinta a la del PdV (36,5)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pos_sale_order(self, sale, lines, *, rate=POS_RATE, **header):
        """Orden del PdV con las líneas ``(sol, producto, precio, extra)`` sin
        precio alterno, ligadas a ``sale``."""
        order = self._order_header(self._new_session(), rate=rate, **header)
        created = self.env["pos.order.line"]
        for sol, product, price, extra in lines:
            vals = self._line_vals(
                order,
                price_unit=price,
                sale_order_origin_id=sale.id,
                sale_order_line_id=sol.id,
                **extra,
            )
            vals["product_id"] = product.id
            created |= self.env["pos.order.line"].create(vals)
        return order, created

    def _invoice(self, order):
        return order._create_invoice(order._prepare_invoice_vals())

    # ------------------------------------------------------------------
    # 1. Anticipo
    # ------------------------------------------------------------------
    def test_downpayment_payment_line_is_filled(self):
        """Pago de un anticipo: línea positiva con alterno 0 -> tasa del PdV."""
        dp_product = self._make_product("Anticipo")
        self.config.down_payment_product_id = dp_product
        sale = self._sale_order(
            [(self.product, 100.0, {}), (dp_product, 30.0, {"is_downpayment": True})]
        )
        dp_sol = sale.order_line[1]
        order, lines = self._pos_sale_order(sale, [(dp_sol, dp_product, 30.0, {})])
        self.assertAlmostEqual(lines.foreign_price, 30.0 * POS_RATE)
        invoice = self._invoice(order)
        invoice_lines = self._invoice_product_lines(invoice)
        self.assertEqual(len(invoice_lines), 1)
        self.assertAlmostEqual(invoice_lines.foreign_price, 30.0 * POS_RATE)
        self.assertAlmostEqual(invoice_lines.foreign_subtotal, 30.0 * POS_RATE)

    def test_settle_remainder_with_negative_downpayment_line(self):
        """Liquidación del resto: producto + anticipo descontado (negativo)."""
        dp_product = self._make_product("Anticipo")
        self.config.down_payment_product_id = dp_product
        sale = self._sale_order(
            [(self.product, 100.0, {}), (dp_product, 30.0, {"is_downpayment": True})]
        )
        sol, dp_sol = sale.order_line
        order, lines = self._pos_sale_order(
            sale,
            [(sol, self.product, 100.0, {}), (dp_sol, dp_product, -30.0, {})],
        )
        product_line, dp_line = lines
        self.assertAlmostEqual(product_line.foreign_price, 100.0 * POS_RATE)
        self.assertAlmostEqual(dp_line.foreign_price, -30.0 * POS_RATE)
        invoice = self._invoice(order)
        by_product = {line.product_id: line for line in self._invoice_product_lines(invoice)}
        self.assertAlmostEqual(by_product[self.product].foreign_price, 100.0 * POS_RATE)
        self.assertAlmostEqual(by_product[dp_product].foreign_price, -30.0 * POS_RATE)
        self.assertAlmostEqual(by_product[dp_product].foreign_subtotal, -30.0 * POS_RATE)

    # ------------------------------------------------------------------
    # 2. Línea partida por lote o por UoM no agrupable
    # ------------------------------------------------------------------
    def test_split_lines_with_same_sale_order_line(self):
        sale = self._sale_order([(self.product, 100.0, {"product_uom_qty": 2})])
        sol = sale.order_line
        order, lines = self._pos_sale_order(
            sale,
            [(sol, self.product, 100.0, {}), (sol, self.product, 100.0, {})],
        )
        self.assertEqual(lines.mapped("sale_order_line_id"), sol)
        for line in lines:
            self.assertAlmostEqual(line.foreign_price, 100.0 * POS_RATE)
        invoice = self._invoice(order)
        invoice_lines = self._invoice_product_lines(invoice)
        self.assertEqual(len(invoice_lines), 2)
        for line in invoice_lines:
            self.assertAlmostEqual(line.foreign_price, 100.0 * POS_RATE)
            self.assertAlmostEqual(line.foreign_subtotal, 100.0 * POS_RATE)

    # ------------------------------------------------------------------
    # 3. Combo
    # ------------------------------------------------------------------
    def test_combo_children_are_filled_and_parent_stays_zero(self):
        child_product = self._make_product("Hija de combo")
        combo = self.env["product.combo"].with_company(self.company).create(
            {
                "name": "Combo prueba",
                "company_id": self.company.id,
                "combo_item_ids": [Command.create({"product_id": child_product.id})],
            }
        )
        combo_product = self._make_product(
            "Combo", type="combo", combo_ids=[Command.set(combo.ids)]
        )
        order = self._order_header(self._new_session(), amount_total=116.0, amount_tax=16.0)
        parent = self.env["pos.order.line"].create(
            self._line_vals(order, price_unit=0.0, product_id=combo_product.id)
        )
        child = self.env["pos.order.line"].create(
            self._line_vals(
                order,
                price_unit=100.0,
                product_id=child_product.id,
                combo_parent_id=parent.id,
                combo_item_id=combo.combo_item_ids.id,
            )
        )
        self.assertEqual(parent.foreign_price, 0.0)
        self.assertAlmostEqual(child.foreign_price, 100.0 * POS_RATE)
        invoice = self._invoice(order)
        product_lines = self._invoice_product_lines(invoice)
        self.assertEqual(product_lines.product_id, child_product)
        for line in product_lines:
            self.assertTrue(line.price_unit and line.foreign_price)
            self.assertAlmostEqual(line.foreign_price, 100.0 * POS_RATE)

    # ------------------------------------------------------------------
    # 4. Reembolso de una orden liquidada
    # ------------------------------------------------------------------
    def test_refund_of_settled_order_reverses_original_foreign_price(self):
        sale = self._sale_order([(self.product, 100.0, {})])
        sol = sale.order_line
        order, lines = self._pos_sale_order(sale, [(sol, self.product, 100.0, {})])
        original_invoice_line = self._invoice_product_lines(self._invoice(order))
        self.assertAlmostEqual(original_invoice_line.foreign_price, 100.0 * POS_RATE)

        # Reembolso desde el PdV a otra tasa, con el alterno en 0.
        refund_order = self._order_header(
            self._new_session(), rate=40.0, name="OL/SALE-R", is_refund=True
        )
        refund_line = self.env["pos.order.line"].create(
            self._line_vals(
                refund_order,
                price_unit=100.0,
                qty=-1.0,
                refunded_orderline_id=lines.id,
                sale_order_origin_id=sale.id,
                sale_order_line_id=sol.id,
            )
        )
        self.assertAlmostEqual(refund_line.foreign_price, 100.0 * POS_RATE)
        credit_note = self._invoice(refund_order)
        credit_lines = self._invoice_product_lines(credit_note)
        self.assertEqual(len(credit_lines), 1)
        self.assertAlmostEqual(credit_lines.foreign_price, original_invoice_line.foreign_price)
        self.assertAlmostEqual(
            credit_lines.foreign_subtotal, original_invoice_line.foreign_subtotal
        )


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_line_foreign_backfill")
class TestPosSaleForeignPriceVesCompany(PosLineForeignPriceHelpers, TestPosSessionAccountingBase):
    """Compañía en Bs (VES) con alterna en USD, como posconsultoria: el diario
    de la factura y la caja están en VES, el multiplicador es 1/600 y la
    precisión "Foreign Product Price" es 2. Aquí sí se asevera el crédito
    alterno de las líneas, la CxC alterna y el balance alterno de la factura."""

    company_currency_name = "VES"
    foreign_currency_name = "USD"
    sales_in_foreign = False

    SALE_RATE = 1 / 600

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tax_8 = cls._make_tax(cls, "VES IVA 8", 8.0)
        cls.tax_22 = cls._make_tax(cls, "VES IVA 22", 22.0)

    def _make_tax(self, name, amount):
        return self.env["account.tax"].create(
            {
                "name": name,
                "amount": amount,
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
                "company_id": self.company.id,
            }
        )

    def setUp(self):
        super().setUp()
        if "sale_order_line_id" not in self.env["pos.order.line"]._fields:
            self.skipTest("pos_sale no está instalado")
        self.env.ref("l10n_ve_accountant.alternative_price_product").digits = 2
        # Tasa del día distinta a la del PdV (600): la factura debe usar la del PdV.
        self._create_rate_of_day(1 / 650)

    def test_settled_sale_order_invoice_foreign_amounts(self):
        self.assertEqual(self.config.currency_id, self.company.currency_id)
        sale = self._sale_order([(self.product, 600.0, {}), (self.product, 1234.56, {})])
        taxes = (self.tax_8, self.tax_22)
        prices = (600.0, 1234.56)
        uuid = "ves-settle-1"
        lines = []
        for index, (sol, price, tax) in enumerate(zip(sale.order_line, prices, taxes)):
            lines.append(
                [
                    0,
                    0,
                    self._sync_line_vals(
                        "%s-%s" % (uuid, index),
                        price,
                        0.0,
                        tax_ids=[(6, 0, tax.ids)],
                        price_subtotal_incl=round(price * (1 + tax.amount / 100), 2),
                        sale_order_line_id=sol.id,
                        sale_order_origin_id=sale.id,
                    ),
                ]
            )
        # 600 + 48 + 1.234,56 + 271,60 = 2.154,16 Bs = 3,59 USD a 600.
        payload = self._sync_payload(
            self._new_session(),
            uuid=uuid,
            rate=self.SALE_RATE,
            lines=lines,
            currency_id=self.company.currency_id.id,
            date_order=fields.Datetime.now(),
            amount_total=2154.16,
            amount_tax=319.60,
            foreign_amount_total=3.59,
        )
        self.env["pos.order"].sync_from_ui([payload])
        order = self.env["pos.order"].search([("uuid", "=", uuid)])
        self.assertEqual(len(order.lines), 2)
        self.assertEqual(order.lines.mapped("foreign_price"), [1.0, 2.06])

        invoice = order._create_invoice(order._prepare_invoice_vals())

        product_lines = self._invoice_product_lines(invoice).sorted("price_unit")
        self.assertEqual(len(product_lines), 2)
        for line, foreign in zip(product_lines, (1.0, 2.06)):
            self.assertAlmostEqual(line.foreign_price, foreign)
            self.assertAlmostEqual(line.foreign_subtotal, foreign)
            self.assertAlmostEqual(line.foreign_credit, foreign)
        tax_lines = invoice.line_ids.filtered(lambda line: line.display_type == "tax")
        # IVA alterno derivado del subtotal alterno: 1,00 x 8 % + 2,06 x 22 %.
        self.assertAlmostEqual(sum(tax_lines.mapped("foreign_credit")), 0.08 + 0.45, places=2)
        receivable = invoice.line_ids.filtered(lambda line: line.display_type == "payment_term")
        self.assertAlmostEqual(
            sum(receivable.mapped("foreign_debit")), order.foreign_amount_total, delta=0.01
        )
        self.assertAlmostEqual(sum(invoice.line_ids.mapped("foreign_balance")), 0.0, places=2)
