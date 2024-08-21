from odoo import models, fields, api

class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    entry_page = fields.Binary(
        string="Portada",
        related='company_id.entry_page',
        readonly=False
    )
    background = fields.Binary(
        string="Fondo",
        related='company_id.background',
        readonly=False
    )
    back_over = fields.Binary(
        string="Contraportada",
        related='company_id.back_over',
        readonly=False
    )
    products_by_page = fields.Integer('Productos por página', related='company_id.products_by_page', readonly=False)
    padding_top = fields.Float('Margin top', related='company_id.padding_top', readonly=False)
    padding_sides = fields.Float('Margin sides', related='company_id.padding_sides', readonly=False)
    border_width = fields.Integer('Border width', related='company_id.border_width', readonly=False)
    primary_color = fields.Char('Primary color', related='company_id.primary_color', readonly=False)

    @api.model
    def set_values(self):
        super(ResConfigSetting, self).set_values()