from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_tax_inside = fields.Boolean(related="company_id.pos_tax_inside", readonly=False)
    pos_move_to_draft = fields.Boolean(related="company_id.pos_move_to_draft", readonly=False)
    pos_show_free_qty = fields.Boolean(related="company_id.pos_show_free_qty", readonly=False)
    pos_show_free_qty_on_warehouse = fields.Boolean(
        related="company_id.pos_show_free_qty_on_warehouse", readonly=False
    )
    amount_to_zero = fields.Boolean(related="pos_config_id.amount_to_zero", readonly=False)
    pos_show_just_products_with_available_qty = fields.Boolean(
        related="company_id.pos_show_just_products_with_available_qty", readonly=False
    )
    pos_search_cne = fields.Boolean(related="company_id.pos_search_cne", readonly=False)
    pos_keep_journal = fields.Boolean(related="pos_config_id.keep_journal", readonly=False)
    pos_unreconcile_moves = fields.Boolean(
        related="company_id.pos_unreconcile_moves", readonly=False
    )
    activate_barcode_strict_mode = fields.Boolean(
        related="pos_config_id.activate_barcode_strict_mode", readonly=False
    )
    sell_kit_from_another_store = fields.Boolean(
        related="pos_config_id.sell_kit_from_another_store", readonly=False
    )
