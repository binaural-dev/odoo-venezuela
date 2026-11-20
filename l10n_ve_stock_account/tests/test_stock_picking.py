from odoo import _, fields
from odoo.tests import Form
from .common import StockAccountCommon
from odoo.exceptions import UserError
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestStockPickingInvoice(StockAccountCommon):
    """Tests for generating invoices from sale orders in Venezuelan localization."""

    def test_01_generate_invoice_from_dispatch_guide(self):
        order = self.create_sale_order()
        order.action_confirm()
        dispatch_guide = order.picking_ids

        for move in dispatch_guide.move_ids_without_package:
            move.quantity = move.product_uom_qty

        dispatch_guide.button_validate()

        invoice = dispatch_guide.create_invoice()

        self.assertTrue(
            len(invoice.invoice_line_ids) == len(order.order_line),
            "The invoice created from the sales orders dispatch guide must have the same number of lines as the sales order.",
        )
        self.assertTrue(
            invoice.picking_ids == dispatch_guide,
            "The invoice must be linked to the dispatch guide from which it was created.",
        )
        _logger.info("test_01_generate_invoice_from_dispatch_guide --- successfully.")

    def test_02_generate_invoice_from_picking(self):
        picking = self.create_picking()
        
        for move in picking.move_ids_without_package:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        self.assertTrue(picking.guide_number, "Debería tener un número de guía generado.")

        invoice = picking.create_invoice()

        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(len(invoice.invoice_line_ids), 1)
        
        line = invoice.invoice_line_ids[0]
        self.assertEqual(line.price_unit, self.product.list_price)
        
        self.assertEqual(picking.state_guide_dispatch, 'invoiced')
        _logger.info("test_02_generate_invoice_from_manual_picking --- successfully.")

    def test_03_generate_invoice_from_picking_maquila(self):
        """Verificar que al generar una factura desde un picking de maquila, no se creen líneas de factura y el estado del picking se actualice a 'invoiced'."""
        picking = self.create_picking("subcontracting")
        
        for move in picking.move_ids_without_package:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        self.assertTrue(picking.guide_number, "Debería tener un número de guía generado.")

        invoice = picking.create_invoice()

        self.assertEqual(invoice.move_type, 'out_invoice')
        self.assertEqual(len(invoice.invoice_line_ids), 0, "No debería crear líneas de factura para movimientos de maquila.")

        self.assertEqual(picking.state_guide_dispatch, 'invoiced')
        _logger.info("test_03_generate_invoice_from_picking_maquila --- successfully.")

    def test_04_transfer_reason_subcontracting_config(self):
        """Verificar que la razón de Maquila se habilite/deshabilite según la compañía"""
        subcontracting_reason = self.env.ref("l10n_ve_stock_account.transfer_reason_subcontracting")
        
        # 2. Crear un picking interno (donde se aplica esta lógica)
        picking = self.create_picking()

        self.company.is_subcontracting = False
        picking._compute_allowed_reason_ids()
        
        self.assertNotIn(
            subcontracting_reason.id, 
            picking.allowed_reason_ids.ids,
            "La razón de Maquila NO debería estar en las permitidas si la configuración está apagada."
        )

        self.company.is_subcontracting = True
        picking._compute_allowed_reason_ids()
        
        self.assertIn(
            subcontracting_reason.id, 
            picking.allowed_reason_ids.ids,
            "La razón de Maquila DEBERÍA estar permitida cuando se activa en la compañía."
        )
        
        _logger.info("test_04_transfer_reason_subcontracting_config --- successfully.")

    def test_05_compute_document_logic(self):
        """Verificar que el documento se fuerce a 'invoice' solo en draft para usuarios con grupo restringido."""
        order_1 = self.create_sale_order(self.user_standard)

        order_1.write({
            'document': 'dispatch_guide',
        })

        order_1.with_user(self.user_standard).action_confirm()
        order_1.with_user(self.user_standard)._compute_document()

        self.assertEqual(order_1.compute_document, 'invoice')
        self.assertEqual(order_1.document, 'dispatch_guide', "Un usuario normal debería poder elegir Guía de Despacho")

        order_2 = self.create_sale_order(self.user_restricted)

        order_2.with_user(self.user_restricted).write({
            'document': 'dispatch_guide',
        })

        # En draft, el usuario restringido debe ser forzado a 'invoice'
        order_2.with_user(self.user_restricted)._compute_document()
        self.assertEqual(order_2.document, 'invoice', "El usuario con grupo especial debe ser forzado a 'invoice' en draft")

        # Al confirmar, _compute_document ya no debe cambiar el documento (state != draft)
        order_2.with_user(self.user_restricted).action_confirm()
        order_2.with_user(self.user_restricted)._compute_document()
        self.assertEqual(order_2.document, 'invoice', "El documento debe mantenerse como 'invoice' incluso después de confirmar")

    def test_06_compute_show_document_visibility(self):
        """Probar la visibilidad del campo según el estado de la orden y el grupo del usuario."""
        
        order_std = self.create_sale_order().with_user(self.user_standard)
        order_std.write({'state': 'draft'})
        self.assertFalse(order_std.show_document, "Usuario estándar no debería ver el documento")

        order_res = self.create_sale_order().with_user(self.user_restricted)
        order_res.write({'state': 'draft'})
        self.assertTrue(order_res.show_document, "Usuario restringido debería ver el documento en borrador")

        order_res.action_confirm()
        self.assertFalse(order_res.show_document, "No se debe mostrar el documento si la orden no está en borrador")

    def test_07_batch_validate_pickings(self):
        """Verificar que validar múltiples pickings en lote no lance error de singleton."""
        reason_transfer = self.env.ref("l10n_ve_stock_account.transfer_reason_transfer_between_warehouses")
        
        # Se crean dos pickings con motivo de transferencia entre almacenes e internos
        picking_1 = self.create_picking(reason_transfer, operation_code="internal")
        picking_2 = self.create_picking(reason_transfer, operation_code="internal")
        
        pickings = picking_1 | picking_2
        
        for move in pickings.move_ids_without_package:
            move.quantity = move.product_uom_qty
            
        # Esto llamará a button_validate() en el recordset de 2 pickings
        pickings.button_validate()
        
        self.assertEqual(picking_1.state, "done")
        self.assertEqual(picking_2.state, "done")
        
        # Verificar que la lógica de state_guide_dispatch = 'emited' se aplicó a ambos
        self.assertEqual(picking_1.state_guide_dispatch, "emited")
        self.assertEqual(picking_2.state_guide_dispatch, "emited")
        _logger.info("test_07_batch_validate_pickings --- successfully.")

    def test_08_return_picking_no_guide_number(self):
        """Verificar que un picking de devolución (is_return=True) no genere correlativo de guía."""
        picking = self.create_picking()
        picking.is_return = True

        for move in picking.move_ids_without_package:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        self.assertFalse(picking.guide_number, "Un picking de devolución no debería generar número de guía.")
        _logger.info("test_08_return_picking_no_guide_number --- successfully.")
