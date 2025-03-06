from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    pos_tax_inside = fields.Boolean()
    pos_show_free_qty = fields.Boolean()
    pos_show_just_products_with_available_qty = fields.Boolean()
    pos_move_to_draft = fields.Boolean()
    pos_search_cne = fields.Boolean()
    pos_unreconcile_moves = fields.Boolean()
    pos_show_free_qty_on_warehouse = fields.Boolean()
