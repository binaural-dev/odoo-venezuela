from odoo import api, fields, models


class Product(models.Model):
    _inherit = "product.product"

    ciu_id = fields.Many2one(
        "economic.activity", string="CIU", compute="_compute_ciu_id", store=True, readonly=False
    )

    @api.depends("categ_id.ciu_id")
    def _compute_ciu_id(self):
        for product in self:
            if product.ciu_id:
                continue
            product.ciu_id = product.categ_id.ciu_id
