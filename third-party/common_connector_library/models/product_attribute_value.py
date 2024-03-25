# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    def get_attribute_values(self, name, attribute_id, auto_create=False):
        """
        Gives attribute value if found, otherwise creates new one and returns it.
        Updated on 15-Feb-2021. In odoo, while search attribute value name('black\') with ilike, it gives an error in
        the search query of odoo.
        :param name: name of attribute value
        :param attribute_id:id of attribute
        :param auto_create: True or False
        :return: attribute values
        """
        attribute_values = self.search([('name', '=', name), ('attribute_id', '=', attribute_id)], limit=1)

        if not attribute_values:
            attribute_values = self.search([('name', '=ilike', name), ('attribute_id', '=', attribute_id)], limit=1)

        if not attribute_values and auto_create:
            return self.create(({'name': name, 'attribute_id': attribute_id}))

        return attribute_values
