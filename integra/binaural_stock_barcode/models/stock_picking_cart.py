from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import random


class StockPickingCart(models.Model):
    _name = "stock.picking.cart"
    _check_company_auto = True
    _description = "Stock Picking Cart"
    _barcode_field = "barcode"

    def _default_barcode(self):
        return self.generate_random_barcode()

    name = fields.Char(string="Description", required=True, copy=False)
    barcode = fields.Char(string="Barcode", required=True, default=_default_barcode, copy=False)
    company_id = fields.Many2one(default=lambda self: self.env.company.id)

    pick_id = fields.Many2one("stock.picking", string="PICK", copy=False)
    pack_id = fields.Many2one("stock.picking", string="PACK", copy=False)
    out_id = fields.Many2one("stock.picking", string="OUT", copy=False)
    warehouse_id = fields.Many2one(
        "stock.warehouse", default=lambda self: self.env.user.property_warehouse_id or self.env.company.main_warehouse_id
    )
    delivery_steps = fields.Selection(related="warehouse_id.delivery_steps")

    @api.onchange("barcode")
    def _onchange_barcode(self):
        if self.barcode and self.env["stock.picking.cart"].search([("barcode", "=", self.barcode)]):
            raise ValidationError(_("Barcode already exists"))

    def generate_random_barcode(self):
        pattern = self.env.ref("binaural_stock_barcode.picking_cart_rule").pattern
        random_barcode = random.randint(100000000, 999999999)
        return str(pattern) + str(random_barcode)

    def set_new_barcode(self):
        barcode = False
        while not barcode:
            gen_barcode = self.generate_random_barcode()
            if not (self.search([("barcode", "=", barcode)]) - self):
                barcode = gen_barcode
        self.barcode = barcode

    def clear_cart(self):
        self.pick_id = False
        self.pack_id = False
        self.out_id = False
