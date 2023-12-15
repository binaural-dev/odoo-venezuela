from odoo import api, fields, models


class Product(models.Model):
    _inherit = "product.template"

    ciu_id = fields.Many2one(
        "economic.activity", string="CIU", compute="_compute_ciu_id", store=True, readonly=False
    )

    ciu_ids = fields.Many2many(
        "economic.activity",
        "product_template_ciu_rel",
        "product_template_id",
        "ciu_id",
        string="CIU",
        # compute="_compute_ciu_ids",
        # store=True,
        # readonly=False,
    )

    @api.depends("categ_id.ciu_id")
    def _compute_ciu_id(self):
        for product in self:
            if product.ciu_id:
                continue
            product.ciu_id = product.categ_id.ciu_id

    @api.depends("categ_id.ciu_id")
    def _compute_ciu_ids(self):
        for product in self:
            if product.ciu_ids:
                continue
            product.ciu_ids += product.categ_id.ciu_id
