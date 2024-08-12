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
import re

from .product_sku_rule import *
from odoo.addons.meli_oerp.models.versions import *

class SaleOrder(models.Model):

    _inherit = "sale.order"

    def _meli_order_update( self, config=None, data=None ):
        #_logger.info("_meli_order_update")
        for order in self:

            wh_id = order._meli_get_warehouse_id(config=config)

            if wh_id:
                order.warehouse_id = wh_id

            #is_full = 'order_json' in data
            if ((order.meli_shipment and order.meli_shipment.logistic_type == "fulfillment")
                or order.meli_shipment_logistic_type=="fulfillment"):
                #seleccionar almacen para la orden
                wh_id = order._meli_get_warehouse_id(config=config)
                if wh_id:
                    order.warehouse_id = wh_id

            order_type = self.env["mercadolibre.orders"].get_sale_order_type( config=config, sale_order=order, shipment=(order and order.meli_shipment) )
            if order_type and "type_id" in order_type:
                order.type_id = order_type["type_id"]
                #_logger.info("order_type:"+str(order_type))

    def meli_deliver( self, meli=None, config=None, data=None):
        _logger.info("meli_deliver stock")
        res= {}
        if "mercadolibre_stock_mrp_production_process" in config._fields and config.mercadolibre_stock_mrp_production_process:
            self.meli_produce( meli=meli, config=config, data=data )

        if self.picking_ids:
            for spick in self.picking_ids:
                _logger.info(spick)
                #if self.warehouse_id and spick.location_id:

                #    if self.warehouse_id.lot_stock_id.id != spick.location_id.id:
                #        _logger.info("Fixing location!")
                #        spick.location_id = self.warehouse_id.lot_stock_id

                #    if self.warehouse_id.lot_stock_id.id != spick.location_id.id:
                #        _logger.info("Fixing location NOT POSSIBLE! Aborting delivery.")
                #        return { "error": "Fixing location NOT POSSIBLE! Aborting delivery." }


                if (spick.move_line_ids):
                    _logger.info(spick.move_line_ids)
                    if (len(spick.move_line_ids)>=1):
                        stock_picking_set_quantities(picking=spick)
                        #_logger.info("validating")
                        try:
                            spick.button_validate()
                            spick.action_done()
                            continue;
                        except Exception as e:
                            _logger.error("stock pick button_validate/action_done error > "+str(e))
                            res = { 'error': str(e) }
                            pass;

                        try:
                            spick.action_assign()
                            spick.button_validate()
                            spick.action_done()
                            continue;
                        except Exception as e:
                            _logger.error("stock pick action_assign/button_validate/action_done error > "+str(e))
                            res = { 'error': str(e) }
                            pass;

    def meli_produce( self, meli=None, config=None, data=None):
        #_logger.info("meli_produce")
        order = self
        productions = self.env['mrp.production'].search( [ ('origin','=',order.name), ('state', 'not in', ['draft','done','cancel']) ])
        if productions:
            for prod in productions:
                _logger.info("meli_produce "+str(prod.name))
                if prod.reservation_state in ['confirmed']:
                    _logger.info("meli_produce (confirmed) action_assign")
                    res = prod.action_assign()
                    _logger.info("meli_produce (confirmed) action_assign res:"+str(res))

                if prod.reservation_state in ['assigned']:
                    _logger.info("meli_produce (assigned) open_produce_product")
                    res = prod.open_produce_product()
                    _logger.info("meli_produce (confirmed) open_produce_product res:"+str(res))

                if prod.state in ['to_close']:
                    _logger.info("meli_produce (to_close) button_mark_down")
                    res = prod.button_mark_done()
                    _logger.info("meli_produce (to_close) button_mark_down res:"+str(res))


    def _meli_get_warehouse_id( self, config=None ):

        company = (config and 'company_id' in config._fields and config.company_id) or self.env.user.company_id
        config = config or company
        wh_id = None

        if (config.mercadolibre_stock_warehouse):
            wh_id = config.mercadolibre_stock_warehouse

        if (self.meli_shipment_logistic_type == "fulfillment"):
            if (config.mercadolibre_stock_warehouse_full):
                wh_id = config.mercadolibre_stock_warehouse_full
        return wh_id

    def confirm_ml_stock( self, meli=None, config=None, force=False ):

        #_logger.info("meli_oerp_stock confirm_ml_stock")
        company = (config and 'company_id' in config._fields and config.company_id) or self.env.user.company_id
        config = config or company

        forcing_date = False
        forcing_date = config and config.mercadolibre_stock_filter_order_datetime and self.meli_date_closed >= config.mercadolibre_stock_filter_order_datetime
        forcing_date = forcing_date and config.mercadolibre_stock_filter_order_datetime_to and self.meli_date_closed <= config.mercadolibre_stock_filter_order_datetime_to

        force = force or forcing_date
        #_logger.info("Forcing shipment validation: "+str(force))

        self._meli_order_update( config=config )

        delinofull = "mercadolibre_order_confirmation_delivery" in config._fields and config.mercadolibre_order_confirmation_delivery
        delifull = "mercadolibre_order_confirmation_delivery_full" in config._fields and config.mercadolibre_order_confirmation_delivery_full
        shipped_or_delivered = self.meli_shipment and ("delivered" in self.meli_shipment.status or "shipped" in self.meli_shipment.status)
        #_logger.info("shipped_or_delivered:"+str(shipped_or_delivered))

        condition = self.meli_shipment_logistic_type=="fulfillment" and delifull and "paid_confirm_deliver" in delifull
        condition = condition or (not self.meli_shipment_logistic_type and delinofull and  "paid_confirm_deliver" in delinofull)

        condition = condition or (self.meli_shipment_logistic_type=="fulfillment" and shipped_or_delivered and delifull and "paid_confirm_shipped_deliver" in delifull)
        condition = condition or (self.meli_shipment_logistic_type=="" and shipped_or_delivered and delinofull and  "paid_confirm_shipped_deliver" in delinofull )
        #last check:
        condition = condition and ("paid" in self.meli_status) and self.state in ['sale','done']


        if self.picking_ids:
            for spick in self.picking_ids:
                _logger.info(spick)
                #if self.warehouse_id and spick.location_id:

                    #if self.warehouse_id.lot_stock_id.id != spick.location_id.id:
                    #    _logger.info("Fixing location!")
                        #spick.location_id = self.warehouse_id.lot_stock_id
                        #if spick.state=="assigned":
                        #    spick.move_line_ids_without_package = None
                        #    spick.do_unreserve()
                        #    if self.warehouse_id.lot_stock_id.id == spick.location_id.id:
                        #        spick.action_assign()

                     #if self.warehouse_id.lot_stock_id.id != spick.location_id.id:
                    #    _logger.info("Fixing location NOT POSSIBLE! Aborting delivery.")
                    #    return { "error": "Fixing location NOT POSSIBLE! Aborting delivery." }


        #_logger.info("delivery condition: "+str(condition))
        if (condition or force):
            self.meli_deliver( meli=meli, config=config)

        #_logger.info("meli_oerp_stock confirm_ml_stock ended")

    #try to update order before confirmation (quotation)
    def confirm_ml( self, meli=None, config=None ):

        #_logger.info("meli_oerp_stock confirm_ml: config:"+str(config and config.name))

        company = (config and 'company_id' in config._fields and config.company_id) or self.env.user.company_id
        config = config or company

        self.confirm_ml_stock( meli=meli, config=config )

        super(SaleOrder, self).confirm_ml( meli=meli, config=config )

        #if self.location_id and self.location_id.mercadolibre_active == True:

        # select lot_id based on max quantity , and assign location_id based on lot_id (search quant assigned... to this lot_id (name) )
        # _logger.info("Location es ML Active "+str(self.location_id))
        #search for the max... check the origin (move_ids.origin)
        # check  and search for lot_id
        # search for stock.quant   related to this location_id, then choose the first bigger lot_id
        # if self.product_id:
        #     quants = self.env["stock.quant"].search([('product_id','=',self.product_id.id),('location_id','=',self.location_id.id)])
            #search max!!!
        #     max = 0
        #     qs = quants and quants[0]
        #     for q in quants:
        #         if q.inventory_quantity>max:
        #             qs = q
        #             max = qs.inventory_quantity
        #     self.lot_id = qs and qs.lot_id
        #

        #seleccionar en la confirmacion del stock.picking la informacion del carrier
        #
        #_logger.info("meli_oerp_stock confirm_ml ended.")


    def ___action_confirm(self):

        _logger.info("order _action_confirm")

        ret = super( SaleOrder, self )._action_confirm()

        _logger.info("order _action_confirm :"+str(self.picking_ids))

        if self.picking_ids:

            for spick in self.picking_ids:

                #_logger.info("_action_confirm Picking state:"+str(spick.state))

                if spick.state in ["assigned"]:

                    _logger.info("_action_confirm picking Asssigned")
                    #for sp in spick.move_line_ids:
                    #    spick.action_assign()
        return ret

    def __action_confirm(self):

        _logger.info("order action_confirm")

        ret = super( SaleOrder, self ).action_confirm()

        _logger.info("order action_confirm :"+str(self.picking_ids)+" ret:"+str(ret))

        if self.picking_ids:

            for spick in self.picking_ids:

                #_logger.info("action_confirm  Picking state:"+str(spick.state))

                if spick.state in ["assigned"]:

                    _logger.info("action_confirm picking Asssigned")
                    #for mv in spick.move_line_ids_without_package:
                    #    _logger.info("Move Line: State:"+str(mv.state)
                    #                +" Product:"+str(mv.product_id and mv.product_id.name)
                    #                +" Location:"+str(mv.location_id and mv.location_id.name)
                    #                +" Lot:"+str(mv.lot_id and mv.lot_id.name)
                    #                +" Qty Reserved:"+str(mv.product_uom_qty)
                    #                )
                    #    #mv.state = 'draft'
                    #spick.do_unreserve()
                    #spick.action_assign()
                    #for mv in spick.move_line_ids_without_package:
                    #    _logger.info("Move Line: State:"+str(mv.state)
                    #                +" Product:"+str(mv.product_id and mv.product_id.name)
                    #                +" Location:"+str(mv.location_id and mv.location_id.name)
                    #                +" Lot:"+str(mv.lot_id and mv.lot_id.name)
                    #                +" Qty Reserved:"+str(mv.product_uom_qty)
                    #                )
                    #spick.action_reassign()
        return ret

class MercadolibreOrder(models.Model):

    _inherit = "mercadolibre.orders"

    #update order after any quotation/order confirmation
    def orders_update_order_json( self, data, context=None, config=None, meli=None ):

        result = super(MercadolibreOrder, self).orders_update_order_json( data=data, context=context, config=config, meli=meli)

        if result and "error" in result and not 'No product related to meli_id' in result['error']:
            return result
        #company = self.env.user.company_id
        oid = (data and 'order_json' in data and 'id' in data['order_json'] and data['order_json']["id"])
        cid = (data and 'id' in data and data['id'])
        if oid or cid:
            order = oid and self.env['mercadolibre.orders'].search([( 'order_id','=',str(oid) )], limit=1)
            order = order or (not order and cid and self.env['mercadolibre.orders'].browse(cid))
            if order:
                sorder = order.sale_order or (order.shipment and order.shipment.sale_order)
                if sorder:
                    sorder._meli_order_update( config=config, data=data )
                else:
                    _logger.info("missing sale order for:"+str(order.name))
            else:
                _logger.info("missing meli order for: oid:"+str(oid)+" or "+str(cid))
        else:
            _logger.info("missing id in data:"+str(data))

        return result

    #mapping procedure params: sku or item
    def map_meli_sku( self, meli_sku=None, meli_item=None ):
        _logger.info("map_meli_sku: "+str(meli_item))
        odoo_sku = None
        mapped_sku = None
        filtered = None
        seller_sku = meli_sku or (meli_item and 'seller_sku' in meli_item and meli_item['seller_sku']) or (meli_item and 'seller_custom_field' in meli_item and meli_item['seller_custom_field'])

        if seller_sku:
            #mapped skus (json dict string assigned)
            if mapping_meli_sku_regex:
                for reg in mapping_meli_sku_regex:
                    rules = mapping_meli_sku_regex[reg]
                    for rule in rules:
                        regex = "regex" in rule and rule["regex"]
                        if regex and not filtered:
                            group = "group" in rule and rule["group"]
                            c = re.compile(regex)
                            if c:
                                ms = c.findall(seller_sku)
                                if ms:
                                    if len(ms)>group:
                                        m = ms[group]
                                        filtered = m
                                        _logger.info("filtered ok: regex: "+str(rule)+" result: "+str(m))
                                        break;

            mapped_sku = (mapping_meli_sku_defaut_code and seller_sku in mapping_meli_sku_defaut_code and mapping_meli_sku_defaut_code[seller_sku])
            mapped_sku = mapped_sku or self.env['meli_oerp.sku.rule'].map_to_sku(name=seller_sku)
            odoo_sku = mapped_sku or filtered or seller_sku

        if mapped_sku:
            _logger.info("map_meli_sku(): meli_sku: "+str(seller_sku)+" mapped to: "+str(odoo_sku))

        return odoo_sku

    #extended from mercadolibre.orders: SKU formulas
    def search_meli_product( self, meli=None, meli_item=None, config=None ):
        _logger.info("search_meli_product extended: "+str(meli_item))
        product_related = super(MercadolibreOrder, self).search_meli_product( meli=meli, meli_item=meli_item, config=config )

        product_obj = self.env['product.product']
        if ( len(product_related)==0 and ('seller_custom_field' in meli_item or 'seller_sku' in meli_item)):

            #Mapping meli sku to odoo sku
            meli_item["seller_sku"] = self.map_meli_sku( meli_item=meli_item )

            #1ST attempt "seller_sku" or "seller_custom_field"
            seller_sku = ('seller_sku' in meli_item and meli_item['seller_sku']) or ('seller_custom_field' in meli_item and meli_item['seller_custom_field'])
            if (seller_sku):
                product_related = product_obj.search([('default_code','=ilike',seller_sku)])

            #2ND attempt only old "seller_custom_field"
            if (not product_related and 'seller_custom_field' in meli_item):
                seller_sku = ('seller_custom_field' in meli_item and meli_item['seller_custom_field'])
            if (seller_sku):
                product_related = product_obj.search([('default_code','=',seller_sku)])
            if not product_related:
                order = self
                order and order.message_post(body=str('seller sku not founded: '+str(seller_sku)))

        #product_obj = self.env['product.product']

        return product_related

    def get_sale_order_type( self, meli=None, order_json=None, config=None, sale_order=None, shipment=None ):

        meli_order_fields =  {}

        if ('sale.order.type' in self.env and sale_order):

            so_type_log_id = None
            so_type_log = None

            #check first for sale_type_id from sale.order > seller team
            so_type_log_id = sale_order and sale_order.team_id and "sale_type_id" in sale_order.team_id._fields and sale_order.team_id.sale_type_id and sale_order.team_id.sale_type_id.id

            so_type_log = self.env['sale.order.type'].search([('name','like','SO-MELI')],limit=1)
            if not so_type_log:
                so_type_log = self.env['sale.order.type'].search([('name','like','SO-MLB')],limit=1)
            if not so_type_log:
                so_type_log = self.env['sale.order.type'].search([('name','like','SO-ECM')],limit=1)

            logistic_type = (shipment and "logistic_type" in shipment._fields and shipment.logistic_type)
            logistic_type = logistic_type or (sale_order and sale_order.meli_shipment_logistic_type)

            if logistic_type:
                #
                if "fulfillment" in logistic_type:
                    so_type_log = self.env['sale.order.type'].search([('name','like','SO-MLF')],limit=1)

            so_type_log_id = so_type_log_id or (so_type_log and so_type_log.id)
            meli_order_fields["type_id"] = so_type_log_id

        return meli_order_fields

    def prepare_sale_order_vals( self, meli=None, order_json=None, config=None, sale_order=None, shipment=None ):
        meli_order_fields = super(MercadolibreOrder, self).prepare_sale_order_vals(meli=meli, order_json=order_json, config=config, sale_order=sale_order, shipment=shipment )
        if ('sale.order.type' in self.env):
            meli_order_fields.update( self.get_sale_order_type(meli=meli, order_json=order_json, config=config, sale_order=sale_order, shipment=shipment) )

        wh_id = None
        if (config.mercadolibre_stock_warehouse):
            wh_id = config.mercadolibre_stock_warehouse
        if (self.shipment_logistic_type == "fulfillment"):
            if (config.mercadolibre_stock_warehouse_full):
                wh_id = config.mercadolibre_stock_warehouse_full
        if wh_id:
            meli_order_fields.update({'warehouse_id': wh_id.id })
        #_logger.info("prepare_sale_order_vals > meli_order_fields:"+str(meli_order_fields))

        return meli_order_fields

#cancelled ship-delivered
#cancelled ship-not_deliveredreturned_to_hub
#cancelled ship-not_deliveredreturning_to_sender
#DEVUELTES
#ni siquiera salio
#cancelled ship-cancelled
