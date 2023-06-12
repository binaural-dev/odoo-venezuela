# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

from odoo import api, models, fields
import logging

_logger = logging.getLogger(__name__)

class ProductTemplateBindToConnector(models.TransientModel):

    _name = "ocapi.binder.wiz"
    _description = "Wizard de Product Template Ocapi Binder"

    connectors = fields.Many2many("ocapi.connection.account", string='Connectors')
    
    def product_template_remove_from_connector(self, context=None):

        context = context or self.env.context

        _logger.info("product_template_remove_from_connector")

        company = self.env.user.company_id
        product_ids = context['active_ids']
        product_obj = self.env['product.template']
        res = {}
        for product_id in product_ids:
            product = product_obj.browse(product_id)
            _logger.info(_("removing product %s") % (product.display_name))
            _logger.info( self.connectors )
            #for conn in self.ocapi_connectors:
                #search in product.ocapi_connection_bindings. the ones with conn.id
                
                #if (conn.id in product.website_sale_shops.ids):
                #    _logger.info("Removing product from website_sale_shop")
                #    product.website_sale_shops = [(3,wss.id)]
#            for wss in self.website_sale_shops:
#                product.write()



    def product_template_add_to_connector(self, context=None):

        context = context or self.env.context

        _logger.info("product_template_add_to_connector")

        company = self.env.user.company_id
        product_ids = context['active_ids']
        product_obj = self.env['product.template']

        res = {}
        for product_id in product_ids:
            product = product_obj.browse(product_id)
            _logger.info(_("adding product %s") % (product.display_name))
            _logger.info(self.connectors)
            #for wss in self.website_sale_shops:
            #    if (wss.id in product.website_sale_shops.ids):
            #        product.website_sale_shops = [(4,wss.id)]
            
            
            
            