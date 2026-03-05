from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = "res.company"

    pos_show_free_qty = fields.Boolean()
    pos_show_just_products_with_available_qty = fields.Boolean()
    pos_move_to_draft = fields.Boolean()
    pos_search_cne = fields.Boolean()
    pos_unreconcile_moves = fields.Boolean()
    pos_show_free_qty_on_warehouse = fields.Boolean()
    
    @api.model
    def _load_pos_data_fields(self, config_id):
        """
        Extend the list of fields to be loaded for the res.company model in the Point of Sale.
        This method ensures that additional fields required for the Venezuelan localization,
        such as taxpayer type and foreign currency, are included in the data sent to the POS frontend.
        """
        
        res = super()._load_pos_data_fields(config_id)
        res +=['taxpayer_type','foreign_currency_id']  
        return res