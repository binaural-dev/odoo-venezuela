from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = "res.company"

    background = fields.Image(string="Fondo")
    entry_page = fields.Image(string="Portada")
    back_over = fields.Image(string="Contraportada")
    products_by_page = fields.Integer('Productos por página', default=9)
    padding_top = fields.Float('Margin top', default=110)
    padding_sides = fields.Float('Margin sides', default=100)
    border_width = fields.Integer('Border width', default=0)
    primary_color = fields.Char('Primary color')
