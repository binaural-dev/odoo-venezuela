from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    check_advance_stock = fields.Boolean(default=False)
    use_fee_percentage = fields.Boolean(default=False)
    apply_fob = fields.Boolean(default=False)
    apply_cif = fields.Boolean(default=False)
    service_products_ids = fields.Many2many(
        "product.product",
        string="Service Products",
        # default=lambda self: self._default_service_product(),
        domain=[('detailed_type','=','service')]
        
    )

    def _default_service_product(self):
        domain=[('detailed_type','=','service')]
        service_products = self.env['product.product'].search(domain)
        return service_products
        
