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
import hashlib
from datetime import datetime


class OcapiConnectionAccount(models.Model):

    _name = "ocapi.connection.account"
    _description = "Odoo Connector Api Account Credentials and Configuration"
    #_inherit = ""

    def get_connector_state(self):
        ocapi_state = True
        for connacc in self:
            connacc.state = ocapi_state

    name = fields.Char(string='Name',index=True, required=True)
    type = fields.Selection([("custom","Custom")],string='Connector',index=True)
    company_id = fields.Many2one("res.company",string="Company",index=True)
    country_id = fields.Many2one("res.country",string="Country",index=True)

    client_id = fields.Char(string='Client Id/App Id', help='Client ID/App Id',size=128,index=True)
    secret_key = fields.Char(string='Secret Key/App Key', help='Secret Key/App Key',size=128,index=True)
    access_token = fields.Text( string='Access Token/Api Token', help='Access Token/Api Token',index=True)
    state = fields.Boolean( compute=get_connector_state, string='State', help="Estado de la conexión", store=False )
    seller_id = fields.Char(string='App Seller Id', help='App Seller Id',size=128,index=True)

    configuration = fields.Many2one( "ocapi.connection.configuration", string="Connection Parameters Configuration", help="Connection Parameters Configuration"  )

    def authorize_token(self, client_id, secret_key ):

        if not secret_key or not client_id or self.client_id != client_id or self.secret_key != secret_key:
            return { "error": "Bad credentials", "message": "Bad credentials, values does not match with any configuration" }

        now = datetime.now()
        date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
        base_str = str(client_id) + str(secret_key) + str(date_time)

        hash = hashlib.blake2b()
        hash.update( base_str.encode() )
        hexhash = hash.hexdigest()

        access_token = hexhash
        self.access_token = access_token

        return access_token

        #self.ocapi_access_token = "
        #self.ocapi_access_token = "MD5ABCDEF0123456789"
    #try to authorize:


    def list_catalog( self, **post ):
        _logger.info("list_catalog")
        result = []
        #catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',self.ids)])
        #catalog = self.env["product.template"].search([])
        bindings = self.env["ocapi.connection.binding.product_template"].search([('connection_account','=',self.id)])
        _logger.info(bindings)
        for bind in bindings:
            _logger.info(bind)

        catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',bindings.ids)])
        for product_tmpl in catalog:
            _logger.info(product_tmpl)
            pjson = {
                "name": product_tmpl.name,
                "sku": product_tmpl.default_code
            }
            result.append(pjson)

        _logger.info(result)
        return result

    def list_pricestock( self, **post ):
        _logger.info("list_pricestock")
        _logger.info(post)
        _logger.info(self)
        result = []
        #catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',self.ids)])
        #catalog = self.env["product.template"].search([])
        bindings = self.env["ocapi.connection.binding.product_template"].search([('connection_account','=',self.id)])
        _logger.info(bindings)
        for bind in bindings:
            _logger.info(bind)

        catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',bindings.ids)])
        for product_tmpl in catalog:
            _logger.info(product_tmpl)
            pjson = {
                "name": product_tmpl.name,
                "sku": product_tmpl.default_code,
            }
            result.append(pjson)

        _logger.info(result)
        return result

    def list_pricelist( self, **post ):
        _logger.info("list_pricelist")
        result = []
        #catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',self.ids)])
        #catalog = self.env["product.template"].search([])
        bindings = self.env["ocapi.connection.binding.product_template"].search([('connection_account','=',self.id)])
        _logger.info(bindings)
        for bind in bindings:
            _logger.info(bind)

        catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',bindings.ids)])
        for product_tmpl in catalog:
            _logger.info(product_tmpl)
            pjson = {
                "name": product_tmpl.name,
                "sku": product_tmpl.default_code,
            }
            result.append(pjson)

        _logger.info(result)
        return result

    def list_stock( self, **post ):
        _logger.info("list_stock")
        result = []
        #catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',self.ids)])
        #catalog = self.env["product.template"].search([])
        bindings = self.env["ocapi.connection.binding.product_template"].search([('connection_account','=',self.id)])
        _logger.info(bindings)
        for bind in bindings:
            _logger.info(bind)

        catalog = self.env["product.template"].search([('ocapi_connection_bindings','in',bindings.ids)])
        for product_tmpl in catalog:
            _logger.info(product_tmpl)
            pjson = {
                "name": product_tmpl.name,
                "sku": product_tmpl.default_code,
            }
            result.append(pjson)

        _logger.info(result)
        return result

    def import_sales( self, **post ):
        _logger.info("import_sales")
        try:
            internals = {
                "connection_account": self,
                "application_id": self.client_id or '',
                "user_id": self.seller_id or '',
                "topic": "sales",
                "resource": "import_sales",
                "state": "PROCESSING"
            }
            noti = self.env["ocapi.connection.notification"].start_internal_notification( internals )
            logs = "to implement"
            errors = "to implement"

            #do all your stuff here...
            #....
            #....

            noti.stop_internal_notification(errors=errors,logs=logs)
        except:
            _logger.error("import_sales error")
            pass;
        result = []
        _logger.info(result)
        return result
