from odoo.tests.common import TransactionCase


class StockAccountCommon(TransactionCase):
    """Compañía venezolana con impuesto, diario de ventas y usuarios para las pruebas de guías."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.company = cls.env.ref("base.main_company")

        ve = cls.env.ref("base.ve")

        cls.company.write(
            {
                "country_id": ve.id,
                "account_fiscal_country_id": ve.id,  # <- clave para la validación de taxes
                "currency_id": cls.currency_vef.id,
                "currency_foreign_id": cls.currency_usd.id,
            }
        )

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Prueba",
                "vat": "J12345678",
                "prefix_vat": "J",
                "country_id": cls.env.ref("base.ve").id,
                "phone": "04141234567",
                "email": "cliente@prueba.com",
                "street": "Calle Falsa 123",
            }
        )

        cls.tax_group = cls.env["account.tax.group"].create(
            {
                "name": "IVA",
                "sequence": 10,
                "country_id": ve.id,
            }
        )

        # Crear impuesto IVA 16%
        cls.tax_iva16 = cls.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": cls.tax_group.id,
                "company_id": cls.company.id,
            }
        )

        # Crear el producto
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "product",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [cls.tax_iva16.id])],
                "detailed_type": "product",
            }
        )

        cls.partner_a = cls.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
            }
        )

        sequence = cls.env["ir.sequence"].create(
            {
                "name": "Secuencia Factura",
                "code": "account.move",
                "prefix": "INV/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )
        refund_sequence = cls.env["ir.sequence"].create(
            {
                "name": "nota de credito",
                "code": "",
                "prefix": "NC/",
                "padding": 8,
                "number_next_actual": 2,
            }
        )

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Diario de Ventas",
                "code": "VEN",
                "type": "sale",
                "sequence_id": sequence.id,
                "refund_sequence_id": refund_sequence.id,
                "company_id": cls.env.company.id,
                "is_contingency": False,
            }
        )
        cls.company.write(
            {
                "customer_journal_id": cls.journal.id,
            }
        )
        cls.tax_purchase_iva16 = cls.env["account.tax"].create(
            {
                "name": "IVA 16% compras",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": cls.tax_group.id,
                "company_id": cls.company.id,
            }
        )
        cls.company.write(
            {
                "account_sale_tax_id": cls.tax_iva16.id,
                "account_purchase_tax_id": cls.tax_purchase_iva16.id,
            }
        )

        # Referencia al grupo de seguridad
        cls.group_not_dispatch = cls.env.ref('l10n_ve_stock_account.group_not_dispatch_guide')
        
        # Grupo de Ventas: Mostrar todos los documentos (para evitar AccessError de Record Rules)
        group_sales_all = cls.env.ref('sales_team.group_sale_salesman_all_leads')
        group_internal_user = cls.env.ref('base.group_user')

        # Crear usuarios con permisos suficientes para ver SOs de otros
        cls.user_standard = cls.env['res.users'].create({
            'name': 'Usuario Estándar',
            'login': 'user_std',
            'email': 'std@test.com',
            'groups_id': [(6, 0, [group_internal_user.id, group_sales_all.id])]
        })

        cls.user_restricted = cls.env['res.users'].create({
            'name': 'Usuario Restringido',
            'login': 'user_res',
            'email': 'res@test.com',
            'groups_id': [(6, 0, [group_internal_user.id, group_sales_all.id, cls.group_not_dispatch.id])]
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

