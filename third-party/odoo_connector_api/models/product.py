# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
#from .warning import warning
import requests


class ProductTemplate(models.Model):

    _inherit = "product.template"

    ocapi_connection_bindings = fields.Many2many( "ocapi.connection.binding.product_template", string="Ocapi Connection Bindings Product Templates" )

    def ocapi_price(self, account):
        return self.lst_price

    def ocapi_stock(self, account):
        return self.virtual_available

class ProductProduct(models.Model):

    _inherit = "product.product"

    ocapi_connection_bindings = fields.Many2many( "ocapi.connection.binding.product", string="Ocapi Connection Bindings Product" )

    def ocapi_price(self, account):
        return self.lst_price

    def ocapi_stock(self, account):
        return self.virtual_available
