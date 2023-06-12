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

import requests
from odoo.addons.meli_oerp.melisdk.meli import Meli
from odoo.addons.meli_oerp.models.versions import *

class product_product(models.Model):

    _inherit = "product.product"

    def _meli_update_logistic_type(self, meli_id=None, meli=False, config=False):
        company = self.env.user.company_id
        product = self
        config = config or company
        company = (config and 'company_id' in config._fields and config.company_id) or company

        meli_util_model = self.env['meli.util']
        if not meli:
            meli = meli_util_model.get_new_instance(company)

        meli_id = meli_id or product.meli_id

        if not meli_id:
            return {}

        try:
            response = meli.get("/items/"+str(meli_id), {'access_token':meli.access_token})
            rjson = response.json()
        except IOError as e:
            _logger.info( "I/O error({0}): {1}".format(e.errno, e.strerror) )
            return {}
        except:
            _logger.info( "Rare error" )
            return {}

        if (rjson and "shipping" in rjson and "logistic_type" in rjson["shipping"]):
            meli_shipping_logistic_type = rjson["shipping"]["logistic_type"]
            if meli_id==product.meli_id:
                product.meli_shipping_logistic_type = meli_shipping_logistic_type

            return meli_shipping_logistic_type
        return ""

    def _meli_get_location_id(self, meli_id=None, meli=False, config=None):

        loc_id = False
        company = self.env.user.company_id
        config = config or company
        company = (config and 'company_id' in config._fields and config.company_id) or company
        meli_id = meli_id or self.meli_id
        meli_shipping_logistic_type = self._meli_update_logistic_type(meli_id=meli_id, meli=meli,config=config)
        #_logger.info("_meli_get_location_id > meli_shipping_logistic_type:"+str(meli_shipping_logistic_type))

        loc_id = self.env["stock.location"].search([('mercadolibre_active','=',True),('company_id', '=', company.id)])
        #loc_id = self.env["stock.location"].search([('mercadolibre_active','=',True)])
        #_logger.info("_meli_get_location_id > loc_id:"+str(loc_id)+ " company:"+str(company.name))

        #CHECK ALL COMPANY LOCATIONS
        if loc_id:
            loc_ids = []
            for lid in loc_id:
                #_logger.info("_meli_get_location_id > lid:"+str(lid.display_name)+" company:"+str(lid.company_id.name)+" log:"+str(lid.mercadolibre_logistic_type) )
                if (meli_shipping_logistic_type != "fulfillment"):
                    if (not lid.mercadolibre_logistic_type or (lid.mercadolibre_logistic_type and 'fulfillment' not in lid.mercadolibre_logistic_type)):
                        loc_ids.append(lid)
                else:
                    if (lid.mercadolibre_logistic_type and 'fulfillment' in lid.mercadolibre_logistic_type):
                        loc_ids.append(lid)
            loc_id = loc_ids
            #_logger.info( "_meli_get_location_id > loc_ids: " + str(loc_id) )

        #JUST OCAPI PUBLISH STOCK LOCATION
        multi_stock_locations = ("publish_stock_locations" in config._fields and config.publish_stock_locations)
        multi_stock_locations = multi_stock_locations or ("mercadolibre_stock_location_to_post_many" in config._fields and config.mercadolibre_stock_location_to_post_many)
        if multi_stock_locations:
            #_logger.info( "_meli_get_location_id > multi_stock_locations: " + str(multi_stock_locations) )
            loc_ids = []
            for lid in multi_stock_locations.filtered(lambda x: not x.company_id or (x.company_id and x.company_id.id == company.id ) ):
                if (meli_shipping_logistic_type != "fulfillment"):
                    if (not lid.mercadolibre_logistic_type or (lid.mercadolibre_logistic_type and 'fulfillment' not in lid.mercadolibre_logistic_type)):
                        loc_ids.append(lid)
                else:
                    if (lid.mercadolibre_logistic_type and 'fulfillment' in lid.mercadolibre_logistic_type):
                        loc_ids.append(lid)
            loc_id = loc_ids
            #_logger.info(loc_id)


        if (meli_shipping_logistic_type == "fulfillment"):
            if (config.mercadolibre_stock_location_to_post_full and not loc_id):
                loc_id = config.mercadolibre_stock_location_to_post_full
            if (config.mercadolibre_stock_warehouse_full and not loc_id):
                loc_id = config.mercadolibre_stock_warehouse_full.lot_stock_id
        else:
            if (config.mercadolibre_stock_location_to_post and not loc_id):
                loc_id = config.mercadolibre_stock_location_to_post
            if (config.mercadolibre_stock_warehouse and not loc_id):
                loc_id = config.mercadolibre_stock_warehouse.lot_stock_id

        return loc_id

    #virtual available from this variant in locations defined on configuration (see _meli_get_location_id)
    def _meli_virtual_available(self, order=None, meli_id=None, meli=False, config=None):

        product_id = self
        company = self.env.user.company_id
        config = config or company
        company = (config and 'company_id' in config._fields and config.company_id) or company
        meli_id = meli_id or self.meli_id
        loc_id = self._meli_get_location_id( meli_id=meli_id, meli=meli,config=config)

        #_logger.info("meli_oerp_stock._meli_virtual_available loc_id: "+str(loc_id))

        quant_obj = self.env['stock.quant']
        #_logger.info("meli_oerp_stock._meli_virtual_available quant_obj: "+str(quant_obj)+" product_id:"+str(product_id))

        qty_available = 0
        #_logger.info("meli_oerp_stock._meli_virtual_available quant_obj: "+str(quant_obj)+" product_id:"+str(product_id))

        loc_oper = ("mercadolibre_stock_location_operation" in config._fields) and config.mercadolibre_stock_location_operation
        qty_method = ("mercadolibre_stock_virtual_available" in config._fields) and config.mercadolibre_stock_virtual_available
        loc_oper = loc_oper or "sum"
        #_logger.info("loc_oper: "+str(loc_oper)+" qty_method: "+str(qty_method))

        last_qty_available_op = 0
        qty_available_op = 0

        for loc in loc_id:

            #Cantidad disponible en esta ubicacion
            if ( not qty_method or qty_method=='virtual' ):
                qty_available_op = quant_obj._get_available_quantity( product_id, loc )
                #_logger.info("qty_available_op virtual: "+str(loc.name)+" "+str(qty_available_op))
            else:
                if (qty_method=='theoretical'):
                    qty_available_op = product_id.get_theoretical_quantity( product_id.id, loc.id )
                    #_logger.info("qty_available_op theoretical: "+str(loc.name)+" "+str(qty_available_op))

                if (qty_method=='qty_reserved'):
                    qty_available_op = product_id.get_theoretical_quantity( product_id.id, loc.id )
                    #_logger.info("qty_available_op qty_reserved: "+str(loc.name)+" "+str(qty_available_op))

            #Operacion entre ubicaciones
            if (loc_oper and loc_oper=="sum" or not loc_oper):
                last_qty_available_op = qty_available_op
                qty_available+= last_qty_available_op

            if loc_oper and loc_oper=="maximum":
                if (qty_available_op>last_qty_available_op):
                    qty_available+= (qty_available_op-last_qty_available_op)
                    last_qty_available_op = qty_available_op

            if loc_oper and loc_oper=="maximum_lot":

                quants = self.env['stock.quant']._gather( product_id, location_id=loc )

                #sum([quant.quantity for quant in quants])
                if ( not qty_method or qty_method=='virtual' ):
                    qty_available_op = (quants and max([(quant.quantity-quant.reserved_quantity) for quant in quants])) or 0
                else:
                    qty_available_op = (quants and max([quant.quantity for quant in quants])) or 0

                if (qty_available_op>last_qty_available_op):
                    qty_available+= (qty_available_op-last_qty_available_op)
                    last_qty_available_op = qty_available_op

            #if loc_oper and loc_oper=="minimum":
            #    if (qty_available_op>0 and qty_available_op<last_qty_available_op):
            #        qty_available+= (qty_available_op-last_qty_available_op)
            #        last_qty_available_op = qty_available_op

            #_logger.info(   "qty_available:"+str(qty_available)
            #                +" last_qty_available_op:"+str(last_qty_available_op)
            #                +" qty_available_op:"+str(qty_available_op) )

        #_logger.info("meli_oerp_stock._meli_virtual_available qty_available: "+str(qty_available))

        return qty_available

    def _meli_available_quantity( self, meli_id=None, meli=False, config=None ):

        #_logger.info("meli_oerp_stock._meli_available_quantity")
        product = self
        product_tmpl = product.product_tmpl_id
        new_meli_available_quantity = product.meli_available_quantity

        meli_id = meli_id or self.meli_id
        #_logger.info("meli_oerp_stock._meli_virtual_available "+str(product._meli_virtual_available()))
        virtual_av = product._meli_virtual_available( meli_id=meli_id, meli=meli, config=config )
        new_meli_available_quantity = virtual_av

        # Chequea si es fabricable
        product_fab = False
        if (1==1 and virtual_av<=0 and product.route_ids):
            for route in product.route_ids:
                if (route.name in ['Fabricar','Manufacture']):
                    #raise ValidationError("Fabricar")
                    #product.meli_available_quantity = product.meli_available_quantity
                    #_logger.info("Fabricar:"+str(new_meli_available_quantity))
                    product_fab = True
            if (not product_fab and product._meli_virtual_available( meli_id=meli_id, meli=meli, config=config )==0):
                new_meli_available_quantity = product._meli_virtual_available( meli_id=meli_id, meli=meli, config=config )

        if (1==1 and 'mrp.bom' in self.env and new_meli_available_quantity<=10000):
            #_logger.info("search bom:"+str(product.default_code))
            bom_id = self.env['mrp.bom'].search([('product_id','=',product.id)],limit=1)
            if not bom_id:
                bom_id = self.env['mrp.bom'].search([('product_tmpl_id','=',product_tmpl.id)],limit=1)
            if bom_id and bom_id.type == 'phantom':
                #_logger.info(bom_id.type)
                #_logger.info("bom_id:"+str(bom_id))
                #chequear si el componente principal es fabricable
                stock_material_max = 100000
                stock_material = 0
                new_meli_available_quantity = 0
                for bom_line in bom_id.bom_line_ids:
                    #if (bom_line.product_id.default_code.find(product_tmpl.code_prefix)==0):
                    if (bom_line.product_id):
                        #_logger.info(product_tmpl.code_prefix)
                        _logger.info("bom product: " + str(bom_line.product_id.default_code) )
                        #for route in product.route_ids:
                            #if (route.name in ['Fabricar','Manufacture']):
                                #_logger.info("Fabricar")
                            #    new_meli_available_quantity = 1
                            #if (route.name in ['Comprar','Buy'] or route.name in ['Fabricar','Manufacture']):
                            #_logger.info("Comprar")
                        virtual_comp_av = bom_line.product_id._meli_virtual_available( meli_id=meli_id, meli=meli,config=config)
                        _logger.info("bom component stock: " + str(virtual_comp_av) )
                        stock_material = virtual_comp_av / bom_line.product_qty
                        if stock_material>=0 and stock_material<=stock_material_max:
                            stock_material_max = stock_material
                            new_meli_available_quantity = stock_material_max
                            _logger.info("stock based on minimum material available / " +str(bom_line.product_qty)+ ": " + str(new_meli_available_quantity))

        return new_meli_available_quantity

    def product_update_stock(self, stock=False, meli=False, config=None):
        product = self
        uomobj = self.env[uom_model]
        _stock = product.virtual_available

        try:
            if (stock!=False):
                _stock = stock
                if (_stock<0):
                    _stock = 0

            if (product.default_code):
                product.set_bom()

            if (product.meli_default_stock_product):
                _stock = product.meli_default_stock_product._meli_available_quantity(meli=meli,config=config)
                if (_stock<0):
                    _stock = 0

            if (1==1 and _stock>=0 and product._meli_available_quantity(meli=meli,config=config)!=_stock):
                _logger.info("Updating stock for variant." + str(_stock) )
                #wh = self.env['stock.location'].search([('usage','=','internal')]).id
                wh = product._meli_get_location_id(meli_id=product.meli_id,meli=meli,config=config)
                _logger.info("Updating stock for variant. location: " + str(wh and wh.display_name) )
                #product_uom_id = uomobj.search([('name','=','Unidad(es)')])
                #if (product_uom_id.id==False):
                #    product_uom_id = 1
                #else:
                #    product_uom_id = product_uom_id.id
                product_uom_id = product.uom_id and product.uom_id.id

                stock_inventory_fields = get_inventory_fields(product, wh)

                _logger.info("stock_inventory_fields:")
                _logger.info(stock_inventory_fields)
                StockInventory = self.env['stock.inventory'].create(stock_inventory_fields)
                #_logger.info("StockInventory:")
                #_logger.info(StockInventory)
                if (StockInventory):
                    stock_inventory_field_line = {
                        "product_qty": _stock,
                        'theoretical_qty': 0,
                        "product_id": product.id,
                        "product_uom_id": product_uom_id,
                        "location_id": wh and wh.id,
                        #'inventory_location_id': wh and wh.id,
                        "inventory_id": StockInventory.id,
                        #"name": "INV "+ nombre
                        #"state": "confirm",
                    }
                    StockInventoryLine = self.env['stock.inventory.line'].create(stock_inventory_field_line)
                    #print "StockInventoryLine:", StockInventoryLine, stock_inventory_field_line
                    _logger.info("StockInventoryLine:")
                    _logger.info(stock_inventory_field_line)
                    if (StockInventoryLine):
                        return_id = stock_inventory_action_done(StockInventory)
                        _logger.info("action_done:"+str(return_id))
        except Exception as e:
            _logger.info("product_update_stock Exception")
            _logger.info(e, exc_info=True)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    #inventory_availability = fields.Selection([
    #    ('never', 'Sell regardless of inventory'),
    #    ('always', 'Show inventory on website and prevent sales if not enough stock'),
    #    ('threshold', 'Show inventory below a threshold and prevent sales if not enough stock'),
    #    ('custom', 'Show product-specific notifications'),
    #], string='Inventory Availability', help='Adds an inventory availability status on the web product page.', default='never')
    #available_threshold = fields.Float(string='Availability Threshold', default=5.0)
    #custom_message = fields.Text(string='Custom Message', default='', translate=True)

    def __get_combination_info(self, combination=False, product_id=False, add_qty=1, pricelist=False, parent_combination=False, only_template=False):

        _logger.info("_get_combination_info meli: "+str(combination))

        combination_info = super(ProductTemplate, self)._get_combination_info(
            combination=combination, product_id=product_id, add_qty=add_qty, pricelist=pricelist,
            parent_combination=parent_combination, only_template=only_template)

        company = self.env.user.company_id
        config = config or company
        company = (config and 'company_id' in config._fields and config.company_id) or company

        use_meli = config and "mercadolibre_stock_website_sale" in config._fields and config.mercadolibre_stock_website_sale

        if not self.env.context.get('website_sale_stock_get_quantity') and not use_meli:
            return combination_info

        _logger.info("combination_info start: "+str(combination_info))

        if combination_info['product_id']:
            product = self.env['product.product'].sudo().browse(combination_info['product_id'])
            website = self.env['website'].get_current_website()
            virtual_available = product.with_context(warehouse=website.warehouse_id.id).virtual_available
            meli_virtual_available = product.with_context(warehouse=website.warehouse_id.id)._meli_virtual_available()
            combination_info.update({
                #'virtual_available': virtual_available,
                'virtual_available': meli_virtual_available,
                'meli_virtual_available': meli_virtual_available,
                'virtual_available_formatted': self.env['ir.qweb.field.float'].value_to_html(meli_virtual_available, {'decimal_precision': 'Product Unit of Measure'}),
                'product_type': product.type,
                'inventory_availability': product.inventory_availability,
                'available_threshold': product.available_threshold,
                'custom_message': product.custom_message,
                'product_template': product.product_tmpl_id.id,
                'cart_qty': product.cart_qty,
                'uom_name': product.uom_id.name,
            })
            _logger.info("combination_info [product_id]: "+str(combination_info))
        else:
            product_template = self.sudo()
            combination_info.update({
                'virtual_available': 0,
                'product_type': product_template.type,
                'inventory_availability': product_template.inventory_availability,
                'available_threshold': product_template.available_threshold,
                'custom_message': product_template.custom_message,
                'product_template': product_template.id,
                'cart_qty': 0
            })

        _logger.info("combination_info final: "+str(combination_info))

        return combination_info
