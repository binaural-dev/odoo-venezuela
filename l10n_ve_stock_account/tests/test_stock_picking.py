import logging
from odoo.tests import TransactionCase, tagged
from odoo import Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestStockPicking(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})
        self.picking_type_out = self.env.ref('stock.picking_type_out')
        self.picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.picking_type_out.default_location_src_id.id,
            'location_dest_id': self.picking_type_out.default_location_dest_id.id,
            'partner_id': self.partner.id,
        })

    def test_get_sequence_guide_num(self):
        self.env['ir.sequence'].search([
            ('code', '=', 'guide.number'),
            ('company_id', '=', self.company.id)
        ]).unlink()
        first = self.picking.get_sequence_guide_num()
        second = self.picking.get_sequence_guide_num()
        self.assertNotEqual(first, second)

    def test_validate_one_invoice_posted(self):
        journal = self.env['account.journal'].create({
            'name': 'Sales Journal',
            'type': 'sale',
            'code': 'SAL',
            'company_id': self.company.id,
        })
        income_account = self.env['account.account'].search([
            ('user_type_id.type', '=', 'other'),
            ('company_id', '=', self.company.id)
        ], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': journal.id,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'account_id': income_account.id,
                    'price_unit': 100,
                    'quantity': 1,
                })
            ],
            'picking_ids': [Command.link(self.picking.id)],
        })
        move.action_post()
        with self.assertRaises(UserError):
            self.picking._validate_one_invoice_posted()

    def test_get_invoice_lines_for_invoice_sale_line_price(self):
        tax = self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale')
        ], limit=1)
        self.company.account_sale_tax_id = tax.id
        product = self.env['product.product'].create({
            'name': 'Prod',
            'type': 'product',
            'list_price': 100,
        })
        sale = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        sale_line = self.env['sale.order.line'].create({
            'order_id': sale.id,
            'product_id': product.id,
            'price_unit': 150,
            'product_uom_qty': 1,
            'name': product.name,
        })
        move = self.env['stock.move'].create({
            'name': product.name,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 1,
            'location_id': self.picking.location_id.id,
            'location_dest_id': self.picking.location_dest_id.id,
            'picking_id': self.picking.id,
            'sale_line_id': sale_line.id,
            'quantity': 1,
        })
        self.picking.sale_id = sale.id
        lines = self.picking._get_invoice_lines_for_invoice()
        self.assertEqual(lines[0][2]['price_unit'], sale_line.price_unit)
