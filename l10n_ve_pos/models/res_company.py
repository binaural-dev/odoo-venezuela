from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    module_binaural_pos_igtf = fields.Boolean("IGTF in POS")
    module_binaural_base_igtf = fields.Boolean("IGTF")
    module_binaural_pos_mf = fields.Boolean("Fiscal Machine")
    module_binaural_pos_advance_payment = fields.Boolean("Advance Payment")
    pos_tax_inside = fields.Boolean()
    pos_show_free_qty = fields.Boolean()
    pos_show_just_products_with_available_qty = fields.Boolean()
    pos_move_to_draft = fields.Boolean()
    pos_search_cne = fields.Boolean()
    pos_unreconcile_moves = fields.Boolean()
    pos_show_free_qty_on_warehouse = fields.Boolean()
