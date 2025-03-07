from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Product(models.Model):
    _inherit = "product.template"

    ciu_ids = fields.Many2many(
        "economic.activity",
        "product_template_ciu_rel",
        "product_template_id",
        "ciu_id",
        string="CIU",
        compute="_compute_ciu_ids",
        store=True,
        readonly=False,
    )

    @api.depends("categ_id.ciu_id")
    def _compute_ciu_ids(self):
        for product in self:
            if product.ciu_ids:
                continue
            product.ciu_ids += product.categ_id.ciu_id

    @api.constrains("ciu_ids")
    def _check_ensure_one_ciu_on_ciu_ids(self):
        for product in self:
            if len(product.ciu_ids) > 1:
                raise ValidationError(
                    _("You cannot select more than one CIU when you have just one subsidiary")
                )
