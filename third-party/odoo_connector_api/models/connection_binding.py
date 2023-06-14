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

class OcapiConnectionBinding(models.Model):

    _name = "ocapi.connection.binding"
    _description = "Ocapi Connection Binding"
    #_inherit = "odoo_connector_api.connection.binding"

    #Connection reference defining mkt place credentials
    connection_account = fields.Many2one( "ocapi.connection.account", string="Odoo Connector Api Connection" )

    #Extern Connection Id binded to this object
    conn_id = fields.Char(string="Connector Id", index=True)

    #Connection Variation Id Binded to this object
    conn_variation_id = fields.Char(string="Connector Variation Id", index=True)

    #Connection Object Class Name to identify object
    class_id = fields.Char(string="Connector Class Id", index=True)

    active = fields.Boolean(string="Active",default=True,index=True)

    def fetch( self, force_update=False ):
        data = {}
        #retreive data from remote database ( Meli: api.mercadolibre.com ; Producteca: last data notification update based on resource value /import_sale/[PR-ID] )
        #Producteca: search last conn_id related to this resource in the notifications

        #MercadoLibre: search last conn_id related to this resource using the REST API (Meli)
        return data

    def refresh( self, data={} ):
        res = {}
        #reprocess the data
        if not (data):
            data = self.fetch()

        #code here...
        #...
        #...

        # # errors:
        # res = { 'error': 'error message' }
        # res = [{ 'error': 'error message' },{ 'error': 'error message 2' },{ 'error': 'error message 3' }]

        # # success:
        # res = True

        return res


class OcapiConnectionBindingProductTemplate(models.Model):

    _name = "ocapi.connection.binding.product_template"
    _description = "Ocapi Product Binding Product Template"
    _inherit = "ocapi.connection.binding"

    #Connection Product Templates Fields binding

    name = fields.Char(string="Name",index=True)
    sku = fields.Char(string="SKU",index=True)
    barcode = fields.Char(string="BARCODE",index=True)

    description = fields.Text(string="Description")

    price = fields.Float(string="Price",index=True)
    stock = fields.Float(string="Stock",index=True)

    full_update = fields.Datetime(string="Product update",index=True)
    image_update = fields.Datetime(string="Image update",index=True)
    price_update = fields.Datetime(string="Price update",index=True)
    stock_update = fields.Datetime(string="Stock update",index=True)

    stock_error = fields.Char(string="Stock Error", index=True )

    attributes = fields.Char(string="Attributes")

    product_tmpl_id = fields.Many2one("product.template",string="Product Template", help="Product Template")
    variant_bindings = fields.One2many("ocapi.connection.binding.product","binding_product_tmpl_id",string="Variant Bindings",help="Variant Bindings")

    image_bindings = fields.One2many('ocapi.product.image', "binding_product_tmpl_id", string="Product Template Images")

    _sql_constraints = [
        ('unique_conn_id_product_tmpl', 'unique(connection_account,conn_id,conn_variation_id,product_tmpl_id)', 'Binding exists for this item: product_tmpl_id!')
    ]

class OcapiConnectionBindingProductVariant(models.Model):

    _name = "ocapi.connection.binding.product"
    _description = "Ocapi Product Binding Product"
    _inherit = "ocapi.connection.binding.product_template"

    binding_product_tmpl_id = fields.Many2one("ocapi.connection.binding.product_template",string="Product Template Binding")
    product_id = fields.Many2one("product.product",string="Product Binding", help="Product Binding")

    image_bindings = fields.One2many('ocapi.product.image', "binding_product_variant_id", string="Product Variant Images")

    _sql_constraints = [
        ('unique_conn_id_variant', 'unique(connection_account,conn_id,conn_variation_id,product_id)', 'Binding exists for this item: product_id!')
    ]




class OcapiConnectionBindingProductCategory(models.Model):

    _name = "ocapi.binding.category"
    _description = "Ocapi Product Binding Category"
    _inherit = "ocapi.connection.binding"

    name = fields.Char(string="Category",index=True)
    category_id = fields.Char(string="Category Id",index=True)

    _sql_constraints = [
        ('unique_conn_id_category', 'unique(connection_account,conn_id,conn_variation_id,category_id)', 'Binding exists for this item: category!')
    ]
