"""Facturación por lotes de varias órdenes (`_create_invoices`).

El override factura por lotes para respetar `max_product_invoice`. Estas
pruebas verifican que, con varias órdenes en la misma llamada (facturación
consolidada), cada lote llama al core una sola vez y ninguna orden se
factura dos veces.
"""

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestConsolidatedInvoices(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company.write({
            "currency_id": self.ves.id,
            "foreign_currency_id": self.usd.id,
        })
        self.env["res.currency.rate"].create({
            "currency_id": self.usd.id,
            "company_id": self.company.id,
            "name": fields.Date.today(),
            "inverse_company_rate": 50.0,
        })
        self.partner = self.env["res.partner"].create({"name": "Partner lotes"})
        self.product = self.env["product.product"].create({
            "name": "Producto lotes",
            "type": "service",
            "invoice_policy": "order",
            "list_price": 100.0,
        })
        self.pl_ves = self.env["product.pricelist"].create({
            "name": "PL lotes VES",
            "currency_id": self.ves.id,
            "company_id": self.company.id,
        })

    def _order(self, lines=1, extra_vals=None, product=None):
        line_vals = [(0, 0, {
            "product_id": (product or self.product).id,
            "product_uom_qty": 1,
            "price_unit": 100.0,
        }) for _ in range(lines)]
        vals = {
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_ves.id,
            "company_id": self.company.id,
            "order_line": line_vals,
        }
        vals.update(extra_vals or {})
        order = self.env["sale.order"].create(vals)
        order.action_confirm()
        return order

    def test_consolidated_normal_orders_one_invoice(self):
        """Dos órdenes facturadas juntas sin agrupar por orden generan una
        sola factura con las líneas de ambas."""
        orders = self._order() | self._order()

        invoices = orders._create_invoices(grouped=False)

        self.assertEqual(len(invoices), 1)
        self.assertEqual(
            invoices.invoice_line_ids.sale_line_ids, orders.order_line
        )

    def test_limit_splits_order_in_batches(self):
        """Una orden que excede `max_product_invoice` se factura en varias
        facturas de a lo sumo el límite de líneas."""
        self.company.max_product_invoice = 2
        order = self._order(lines=5)

        invoices = order._create_invoices()

        self.assertEqual(len(invoices), 3)
        self.assertEqual(
            sorted(len(inv.invoice_line_ids) for inv in invoices), [1, 2, 2]
        )
        self.assertEqual(order.invoice_status, "invoiced")

    def test_order_with_note_one_invoice(self):
        """Una nota en la orden no cuenta como línea pendiente: se crea una
        sola factura y no se vuelve a llamar al core."""
        order = self._order()
        order.order_line = [(0, 0, {
            "display_type": "line_note",
            "name": "Nota",
        })]

        invoices = order._create_invoices()

        self.assertEqual(len(invoices), 1)

    def test_consolidated_normal_order_with_subscription(self):
        """Una orden normal procesada antes que una suscripción, facturadas
        juntas, generan una sola factura: la línea recurrente sigue saliendo
        como facturable mientras su factura está en borrador y no debe
        facturarse de nuevo."""
        if "sale.subscription.plan" not in self.env:
            self.skipTest("Requiere el módulo sale_subscription")
        plan = self.env["sale.subscription.plan"].create({
            "name": "Plan mensual lotes",
            "billing_period_value": 1,
            "billing_period_unit": "month",
        })
        recurring = self.env["product.product"].create({
            "name": "Servicio recurrente lotes",
            "type": "service",
            "invoice_policy": "order",
            "recurring_invoice": True,
            "list_price": 100.0,
        })
        subscription = self._order(
            product=recurring, extra_vals={"plan_id": plan.id}
        )
        normal = self._order()

        invoices = (normal | subscription)._create_invoices(grouped=False)

        self.assertEqual(len(invoices), 1)
        self.assertEqual(
            invoices.invoice_line_ids.sale_line_ids,
            (normal | subscription).order_line,
        )
