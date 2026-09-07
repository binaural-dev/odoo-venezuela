"""Cobertura de la funcionalidad descrita en el README del modulo.

Los demas archivos cubren la tasa de cambio y el recalculo de la factura.
Este cubre lo que el README documenta y no estaba verificado: los montos
alternos de cabecera, el subtotal alterno de la linea y los controles de
negocio sobre la confirmacion del pedido.
"""

import logging

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestDocumentedBehaviour(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company.write({
            "currency_id": self.ves.id,
            "foreign_currency_id": self.usd.id,
        })
        self.today = fields.Date.today()
        self._set_rate(self.usd, self.today, 50.0)

        self.partner = self.env["res.partner"].create({"name": "Partner doc"})
        self.product = self.env["product.product"].create({
            "name": "Producto doc",
            "list_price": 100.0,
        })
        self.pl_ves = self.env["product.pricelist"].create({
            "name": "PL doc VES",
            "currency_id": self.ves.id,
            "company_id": self.company.id,
        })
        self.tax_group = self.env["account.tax.group"].search([], limit=1)
        self.tax_16 = self.env["account.tax"].create({
            "name": "IVA 16% doc",
            "amount": 16.0,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        })

    def _set_rate(self, currency, date, ves_per_unit):
        rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", currency.id),
            ("company_id", "=", self.company.id),
            ("name", "=", date),
        ], limit=1)
        if rate:
            rate.inverse_company_rate = ves_per_unit
            return rate
        return self.env["res.currency.rate"].create({
            "currency_id": currency.id,
            "company_id": self.company.id,
            "name": date,
            "inverse_company_rate": ves_per_unit,
        })

    def _order(self, lines=None, price_unit=1000.0, taxes=True):
        line_vals = lines or [(0, 0, {
            "product_id": self.product.id,
            "product_uom_qty": 1,
            "price_unit": price_unit,
            "tax_ids": [(6, 0, [self.tax_16.id])] if taxes else [(5, 0, 0)],
        })]
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_ves.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": line_vals,
        })

    # ── montos alternos de la cabecera ───────────────────────────────

    def test_foreign_taxable_income_is_the_alternate_tax_base(self):
        """foreign_taxable_income es la base imponible en moneda alterna y
        sale de tax_totals, igual que el resto de totales."""
        order = self._order(price_unit=1000.0)

        tax_totals = order.tax_totals if isinstance(order.tax_totals, dict) else {}
        self.assertAlmostEqual(
            order.foreign_taxable_income,
            tax_totals.get("base_amount_foreign_currency", 0),
            places=2,
            msg="foreign_taxable_income debe leerse de tax_totals"
        )
        # 1.000 Bs a tasa 50 = 20 USD de base
        self.assertAlmostEqual(order.foreign_taxable_income, 20.0, places=2)

    def test_foreign_totals_include_taxes_only_in_the_total(self):
        """El subtotal alterno es la base y el total alterno lleva el impuesto:
        con IVA 16%, total = base * 1,16."""
        order = self._order(price_unit=1000.0)

        self.assertAlmostEqual(order.foreign_untaxed_total, 20.0, places=2)
        self.assertAlmostEqual(order.foreign_total_billed, 23.2, places=2)

    def test_signed_totals_are_in_company_currency(self):
        """Los totales _signed estan en moneda de la compania: con el pedido ya
        en esa moneda, coinciden con los del documento."""
        order = self._order(price_unit=1000.0)

        self.assertAlmostEqual(
            order.amount_untaxed_total_signed, order.amount_untaxed, places=2
        )
        self.assertAlmostEqual(
            order.amount_total_signed, order.amount_total, places=2
        )

    # ── subtotal alterno de la linea ─────────────────────────────────

    def test_line_foreign_subtotal_excludes_taxes(self):
        """foreign_subtotal de la linea es la base sin impuestos, calculada con
        compute_all, y el precio alterno respeta la cantidad."""
        order = self._order(lines=[(0, 0, {
            "product_id": self.product.id,
            "product_uom_qty": 3,
            "price_unit": 1000.0,
            "tax_ids": [(6, 0, [self.tax_16.id])],
        })])
        line = order.order_line

        # 1.000 Bs / 50 = 20 USD por unidad
        self.assertAlmostEqual(line.foreign_price, 20.0, places=4)
        # y el subtotal son 3 unidades SIN impuesto
        self.assertAlmostEqual(line.foreign_subtotal, 60.0, places=2)

    def test_line_foreign_subtotal_applies_the_discount(self):
        """El descuento de la linea se refleja en el subtotal alterno."""
        order = self._order(lines=[(0, 0, {
            "product_id": self.product.id,
            "product_uom_qty": 2,
            "price_unit": 1000.0,
            "discount": 10.0,
            "tax_ids": [(6, 0, [self.tax_16.id])],
        })])

        # 2 x 20 USD con 10% de descuento = 36 USD
        self.assertAlmostEqual(order.order_line.foreign_subtotal, 36.0, places=2)

    # ── controles de negocio sobre la confirmacion ───────────────────

    def test_line_limit_blocks_confirmation(self):
        """are_sale_lines_limited + maximum_sales_line_limit impiden confirmar
        un pedido con mas lineas de las permitidas."""
        self.company.write({
            "are_sale_lines_limited": True,
            "maximum_sales_line_limit": 2,
        })
        order = self._order(lines=[
            (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                    "price_unit": 100.0}) for _ in range(3)
        ])

        with self.assertRaises(UserError):
            order.action_confirm()

    def test_line_limit_allows_orders_within_the_limit(self):
        """Con el limite activo, un pedido dentro del maximo se confirma."""
        self.company.write({
            "are_sale_lines_limited": True,
            "maximum_sales_line_limit": 5,
        })
        order = self._order(lines=[
            (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                    "price_unit": 100.0}) for _ in range(3)
        ])

        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_line_limit_ignored_when_disabled(self):
        """Sin la opcion activa el numero de lineas no se controla."""
        self.company.write({
            "are_sale_lines_limited": False,
            "maximum_sales_line_limit": 1,
        })
        order = self._order(lines=[
            (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                    "price_unit": 100.0}) for _ in range(4)
        ])

        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_cannot_confirm_an_order_without_lines(self):
        """Un pedido sin lineas de producto no se puede confirmar."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_ves.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
        })

        with self.assertRaises(UserError):
            order.action_confirm()

    def test_storable_without_stock_blocks_confirmation(self):
        """not_allow_sell_products impide confirmar un pedido con un producto
        almacenable sin existencias suficientes."""
        self.company.not_allow_sell_products = True
        storable = self.env["product.product"].create({
            "name": "Almacenable doc",
            "is_storable": True,
            "type": "consu",
            "list_price": 100.0,
        })
        order = self._order(lines=[(0, 0, {
            "product_id": storable.id,
            "product_uom_qty": 10,
            "price_unit": 100.0,
        })])

        with self.assertRaises(ValidationError):
            order.action_confirm()

    # ── estado de facturacion de la linea ────────────────────────────

    def test_line_invoiced_flag(self):
        """`invoiced` marca la linea cuando toda su facturacion son facturas
        de cliente."""
        order = self._order(price_unit=1000.0)
        order.action_confirm()
        self.assertFalse(order.order_line.invoiced)

        order._create_invoices()
        self.assertTrue(
            order.order_line.invoiced,
            "Tras facturar, la linea debe quedar marcada como facturada"
        )
