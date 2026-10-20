# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.fields import Command


@tagged('post_install', '-at_install')
class TestCreateInvoicesNoteLines(TransactionCase):
    """Regresión del loop de `_create_invoices`: las líneas de nota cuentan
    siempre como "invoiceable" para el core, así que el while que reparte la
    facturación por lotes (max_product_invoice) re-entraba después del último
    lote con solo la nota restante y el core reventaba con "No items are
    available to invoice"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente Nota l10n_ve'})
        cls.product_a = cls.env['product.product'].create({
            'name': 'Producto A Nota',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 100.0,
        })
        cls.product_b = cls.env['product.product'].create({
            'name': 'Producto B Nota',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 50.0,
        })

    def _create_order(self, products):
        lines = [
            Command.create({'product_id': product.id, 'product_uom_qty': 1})
            for product in products
        ]
        lines.append(Command.create({'display_type': 'line_note', 'name': 'Nota de entrega'}))
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': lines,
        })
        order.action_confirm()
        return order

    def test_01_create_invoices_with_note_line(self):
        """Una orden con línea de nota debe facturarse en un solo pase, sin
        que el loop re-entre por la nota y reviente."""
        order = self._create_order([self.product_a])

        invoices = order._create_invoices()

        self.assertEqual(len(invoices), 1)
        self.assertFalse(
            order._get_invoiceable_lines().filtered(lambda line: not line.display_type),
            "No deberían quedar líneas de producto por facturar",
        )

    def test_02_create_invoices_multi_batch_with_note_line(self):
        """El caso para el que existe el while: con max_product_invoice bajo
        la orden se factura en varios lotes, y la nota tampoco debe hacer que
        el loop siga después del último lote."""
        self.env.company.max_product_invoice = 1
        order = self._create_order([self.product_a, self.product_b])

        invoices = order._create_invoices()

        self.assertEqual(len(invoices), 2, "Dos productos con límite 1 son dos facturas")
        self.assertFalse(
            order._get_invoiceable_lines().filtered(lambda line: not line.display_type),
            "No deberían quedar líneas de producto por facturar",
        )
