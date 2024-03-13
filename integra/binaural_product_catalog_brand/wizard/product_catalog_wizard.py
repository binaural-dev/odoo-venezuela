from odoo import models, fields, api


class GenerateProductCatalogWizard(models.TransientModel):
    _inherit = "product.catalog.wizard"
    _description = "Product Catalog Wizard"

    show_brand = fields.Boolean(string="Show brand")
