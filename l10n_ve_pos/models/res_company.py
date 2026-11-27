from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = "res.company"

    pos_show_free_qty = fields.Boolean()
    pos_show_just_products_with_available_qty = fields.Boolean()
    pos_move_to_draft = fields.Boolean()
    pos_search_cne = fields.Boolean()
    pos_unreconcile_moves = fields.Boolean()
    pos_show_free_qty_on_warehouse = fields.Boolean()
    pos_post_cross_moves = fields.Boolean(
        string="Post PoS Cross Moves",
        default=True,
        help="Post the PoS cross moves as soon as they are created, with the statement "
        "line of the real journal reconciled against them. Unchecked, they are left "
        "in draft and that happens when accounting posts them.",
    )
    
    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        res +=['taxpayer_type','foreign_currency_id']  
        return res