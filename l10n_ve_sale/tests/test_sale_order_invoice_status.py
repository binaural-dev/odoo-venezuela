# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.fields import Command


class TestSaleOrderInvoiceStatus(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.customer = cls.env['res.partner'].create({'name': 'Cliente Prueba l10n_ve'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto de Prueba',
            'type': 'consu',
            'invoice_policy': 'delivery',
        })

    def test_01_partially_billed_status(self):
        """Validar que el estado cambie a 'partially_billed' cuando se factura menos de lo entregado."""
        sale_order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 10,
            })],
        })
        sale_order.action_confirm()
        self.assertEqual(sale_order.state, 'sale')

        picking = sale_order.picking_ids
        picking.move_ids.quantity = 10
        picking.button_validate()
        self.assertEqual(sale_order.order_line.qty_delivered, 10)

        context = {
            'active_model': 'sale.order',
            'active_ids': [sale_order.id],
            'active_id': sale_order.id,
        }
        payment_wizard = self.env['sale.advance.payment.inv'].with_context(context).create({
            'advance_payment_method': 'delivered',
        })
        payment_wizard.create_invoices()

        invoice = sale_order.invoice_ids
        invoice.invoice_line_ids.write({'quantity': 5})
        invoice.action_post()

        sale_order._compute_invoice_status()

        self.assertEqual(
            sale_order.invoice_status,
            'partially_billed',
            "El estado debería ser 'partially_billed' porque facturamos 5 y entregamos 10"
        )
