from odoo import _, fields
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from odoo.tests import tagged
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestStockPickingInvoice(TransactionCase):
    """Tests for generating invoices from sale orders in Venezuelan localization."""

    def setUp(self):
        super(TestStockPickingInvoice, self).setUp()
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")

        ve = self.env.ref("base.ve")

        self.company.write(
            {
                "country_id": ve.id,
                "account_fiscal_country_id": ve.id,  # <- clave para la validación de taxes
                "currency_id": self.currency_vef.id,
                "currency_foreign_id": self.currency_usd.id,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente Prueba",
                "vat": "J12345678",
                "prefix_vat": "J",
                "country_id": self.env.ref("base.ve").id,
                "phone": "04141234567",
                "email": "cliente@prueba.com",
                "street": "Calle Falsa 123",
            }
        )

        self.tax_group = self.env["account.tax.group"].create(
            {
                "name": "IVA",
                "sequence": 10,
                "country_id": ve.id,
            }
        )

        # Crear impuesto IVA 16%
        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
                "company_id": self.company.id,
            }
        )

        # Crear el producto
        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "product",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
                "detailed_type": "product",
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
            }
        )

        sequence = self.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        refund_sequence = self.env["ir.sequence"].create(
            {
                "name": "nota de credito",
                "code": "",
                "prefix": "NC/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        self.journal = self.env["account.journal"].create(
            {
                "name": "Diario de Ventas",
                "code": "VEN",
                "type": "sale",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": self.env.company.id,
                "is_contingency": False,
            }
        )
        self.company.write(
            {
                "customer_journal_id": self.journal.id,
            }
        )

        # Referencia al grupo de seguridad
        self.group_not_dispatch = self.env.ref('l10n_ve_stock_account.group_not_dispatch_guide')
        
        # Grupo de Ventas: Mostrar todos los documentos (para evitar AccessError de Record Rules)
        group_sales_all = self.env.ref('sales_team.group_sale_salesman_all_leads')
        group_internal_user = self.env.ref('base.group_user')

        # Crear usuarios con permisos suficientes para ver SOs de otros
        self.user_standard = self.env['res.users'].create({
            'name': 'Usuario Estándar',
            'login': 'user_std',
            'email': 'std@test.com',
            'groups_id': [(6, 0, [group_internal_user.id, group_sales_all.id])]
        })

        self.user_restricted = self.env['res.users'].create({
            'name': 'Usuario Restringido',
            'login': 'user_res',
            'email': 'res@test.com',
            'groups_id': [(6, 0, [group_internal_user.id, group_sales_all.id, self.group_not_dispatch.id])]
        })

    def create_sale_order(self, user=None):
        env = self.env if user is None else self.env(user=user)
        rate = 5.0
        order = env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "manually_set_rate": True,
                "foreign_rate": rate,
                "foreign_inverse_rate": 1 / rate,
                "document": "dispatch_guide",
            }
        )

        order_line_01 = env["sale.order.line"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "price_unit": 100,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": rate,
                "display_type": False,
                "name": "Test Product Line",
            }
        )

        order_line_02 = env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_section",
                "name": "Section Line",
            }
        )

        order_line_03 = env["sale.order.line"].create(
            {
                "product_id": False,
                "product_uom_qty": 0,
                "price_unit": 0,
                "tax_id": [(6, 0, [self.tax_iva16.id])],
                "order_id": order.id,
                "currency_id": self.currency_vef.id,
                "foreign_currency_id": self.currency_usd.id,
                "foreign_rate": 0,
                "display_type": "line_note",
                "name": "Section Line",
            }
        )

        order.write(
            {
                "order_line": [order_line_01.id, order_line_02.id, order_line_03.id],
            }
        )
        return order

    def create_picking(self, trasfer_reason_id=None, operation_code='outgoing'):
        if isinstance(trasfer_reason_id, str):
            trasfer_reason_id = self.env['transfer.reason'].search([('code', '=', trasfer_reason_id)], limit=1)

        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        
        # Búsqueda del tipo de operación (outgoing, internal, etc)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', operation_code), 
            ('warehouse_id', '=', warehouse.id)
        ], limit=1)
        
        if not picking_type:
            # Creación automática si no existe en DB limpia
            picking_type = self.env['stock.picking.type'].create({
                'name': f'Test {operation_code}',
                'code': operation_code,
                'warehouse_id': warehouse.id,
                'sequence_code': 'TEST',
                'reservation_method': 'at_confirm',
            })

        loc_id = picking_type.default_location_src_id.id or warehouse.lot_stock_id.id
        loc_dest_id = picking_type.default_location_dest_id.id or (self.env.ref('stock.stock_location_customers').id if operation_code == 'outgoing' else warehouse.lot_stock_id.id)

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': picking_type.id,
            'location_id': loc_id,
            'location_dest_id': loc_dest_id,
            'origin': 'Manual Test Picking',
            'transfer_reason_id': trasfer_reason_id.id if trasfer_reason_id else False,
            'is_dispatch_guide': True,
        })

        self.env['stock.move'].create({
            'name': self.product.name,
            'product_id': self.product.id,
            'product_uom_qty': 10.0,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })
        
        return picking

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
        """Verificar que el documento se fuerce a 'invoice' si el usuario tiene el grupo restringido."""
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
        order_2.with_user(self.user_restricted).action_confirm()
        order_2.with_user(self.user_restricted)._compute_document()

        self.assertEqual(order_2.document, 'invoice', "El usuario con el grupo especial debe ser forzado a tener 'invoice'")

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
