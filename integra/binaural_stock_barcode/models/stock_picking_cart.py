from odoo import fields, models
import random


class StockPickingCart(models.Model):
    _name = "stock.picking.cart"

    def _default_barcode(self):
        return self.generate_random_barcode()

    name = fields.Char(string="Description", required=True)
    barcode = fields.Char(string="Barcode", required=True, default=_default_barcode)

    pick_id = fields.Many2one("stock.picking", string="PICK")
    pack_id = fields.Many2one("stock.picking", string="PACK")
    out_id = fields.Many2one("stock.picking", string="OUT")

    def generate_random_barcode(self):
        pattern = self.env.ref("binaural_stock_barcode.picking_cart_rule").pattern
        random_barcode = random.randint(100000000, 999999999)
        return str(pattern) + str(random_barcode)

    def set_new_barcode(self):
        self.barcode = self.generate_random_barcode()
