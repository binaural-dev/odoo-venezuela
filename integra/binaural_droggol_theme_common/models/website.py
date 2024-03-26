from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.tools.translate import html_translate
import logging

_logger = logging.getLogger(__name__)

class Website(models.Model):
    _inherit = 'website'

    def _get_brands(self, domain=[], limit=None, order=None):
        brand_attributes = self._get_brand_attributes().ids
        domain = expression.AND([domain, [('attribute_id', 'in', brand_attributes), ('company_id', '=', self.env.company.id)]])
        return self.env['product.attribute.value'].search(domain, limit=limit, order=order)

    def _get_brand_attributes(self):
        """ This will preserver the sequence """
        current_website_products = self.env['product.template'].search(self.sale_product_domain())
        all_brand_attributes = self.env['product.template']._get_brand_attribute()
        return self.env['product.template.attribute.line'].search([('product_tmpl_id', 'in', current_website_products.ids),('attribute_id', 'in', all_brand_attributes.ids)]).mapped('attribute_id')