from odoo import fields, models


class StockPickingCart(models.Model):
    _name = "stock.picking.cart"

    name = fields.Char(string="Description", required=True)
    barcode = fields.Char(string="Barcode", required=True)

    pick_id = fields.Many2one("stock.picking", string="PICK")
    pack_id = fields.Many2one("stock.picking", string="PACK")
    out_id = fields.Many2one("stock.picking", string="OUT")

