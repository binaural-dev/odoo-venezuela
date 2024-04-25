# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    def get_attribute(self, attribute_string, attribute_type='radio', create_variant='always', auto_create=False):
        """
        Gives attribute if found, otherwise creates new one and returns it.
        :param attribute_string: name of attribute
        :param attribute_type: type of attribute
        :param create_variant: when variant create
        :param auto_create: True or False
        :return: attributes
        """
        attributes = self.search([('name', '=ilike', attribute_string),
                                  ('create_variant', '=', create_variant)], limit=1)
        if not attributes and auto_create:
            return self.create(({'name': attribute_string, 'create_variant': create_variant,
                                 'display_type': attribute_type}))
        return attributes
