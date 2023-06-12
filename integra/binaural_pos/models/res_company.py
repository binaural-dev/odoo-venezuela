from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    module_binaural_pos_igtf = fields.Boolean("IGTF in POS")
    module_binaural_base_igtf = fields.Boolean("IGTF")
    module_binaural_pos_mf = fields.Boolean("Fiscal Machine")
    pos_tax_inside = fields.Boolean()
    pos_show_free_qty = fields.Boolean()
