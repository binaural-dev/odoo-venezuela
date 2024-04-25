# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def write(self, vals):
        """
        This method use to archive/unarchive shopify product templates base on odoo product templates.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 09/12/2019.
        :Task id: 158502
        """
        if 'active' in vals.keys():
            shopify_product_template_obj = self.env['shopify.product.template.ept']
            for template in self:
                shopify_templates = shopify_product_template_obj.search(
                    [('product_tmpl_id', '=', template.id)])
                if vals.get('active'):
                    shopify_templates = shopify_product_template_obj.search(
                        [('product_tmpl_id', '=', template.id), ('active', '=', False)])
                shopify_templates.write({'active': vals.get('active')})
        res = super(ProductTemplate, self).write(vals)
        return res


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def write(self, vals):
        """
        This method use to archive/unarchive shopify product base on odoo product.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 30/03/2019.
        """
        if 'active' in vals.keys():
            shopify_product_product_obj = self.env['shopify.product.product.ept']
            for product in self:
                shopify_product = shopify_product_product_obj.search(
                    [('product_id', '=', product.id)])
                if vals.get('active'):
                    shopify_product = shopify_product_product_obj.search(
                        [('product_id', '=', product.id), ('active', '=', False)])
                shopify_product.write({'active': vals.get('active')})
        res = super(ProductProduct, self).write(vals)
        return res
