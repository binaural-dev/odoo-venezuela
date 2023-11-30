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
        domain=[('detailed_type','=','service')]
        
    )

    check_calculate_taking_order_quantities = fields.Boolean(default=False)
    check_calculate_based_total_purchase_amount = fields.Boolean(default=False)

    def _default_service_product(self):
        domain=[('detailed_type','=','service')]
        service_products = self.env['product.product'].search(domain)
        return service_products
        
