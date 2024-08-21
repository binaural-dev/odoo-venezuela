from odoo import models, fields, api

class ProductCatalog(models.Model):
    _inherit = "product.catalog"

    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company.id)

    entry_page = fields.Image(
        string="Portada",
        related='company_id.entry_page',
        readonly=False
    )

    background = fields.Image(
        string="Fondo",
        related='company_id.background',
        readonly=False
    )

    back_over = fields.Image(
        string="Contraportada",
        related='company_id.back_over',
        readonly=False
    )
