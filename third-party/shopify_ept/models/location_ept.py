# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import time
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

class ShopifyLocationEpt(models.Model):
    _name = 'shopify.location.ept'
    _description = 'Shopify Stock Location'

    name = fields.Char(help="Give this location a short name to make it easy to identify. You’ll see this name in areas"
                            "like orders and products.",
                       readonly="1")
    export_stock_warehouse_ids = fields.Many2many('stock.warehouse', string='Warehouses',
                                                  help="Selected warehouse used while Export the stock.")
    import_stock_warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse',
                                                help="Selected warehouse used while Import the stock.")
    shopify_location_id = fields.Char(readonly="1")
    instance_id = fields.Many2one('shopify.instance.ept', "Instance", readonly="1", ondelete="cascade")
    legacy = fields.Boolean('Is Legacy Location', help="Whether this is a fulfillment service location. If true, then"
                                                       "the location is a fulfillment service location. If false, then"
                                                       "the location was created by the merchant and isn't tied to a"
                                                       "fulfillment service.", readonly="1")
    is_primary_location = fields.Boolean(readonly="1")
    shopify_instance_company_id = fields.Many2one('res.company', string='Company', readonly=True)
    warehouse_for_order = fields.Many2one('stock.warehouse', "Warehouse in Order",
                                          help="The warehouse to set while importing order, if this"
                                               " Shopify location is found.")
    active = fields.Boolean(default=True)

    @api.constrains('export_stock_warehouse_ids')
    def _check_locations_warehouse_ids(self):
        """Not allow to set warehouse in export warehouses in the Shopify location,
           if warehouse already set in a different location with the same instance.
           @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 07/11/2019.
           :Task ID: 157407
        """
        location_instance = self.instance_id
        location_warehouse = self.export_stock_warehouse_ids
        locations = self.search([('instance_id', '=', location_instance.id), ('id', '!=', self.id)])
        for location in locations:
            if any([location in location_warehouse.ids for location in location.export_stock_warehouse_ids.ids]):
                raise ValidationError(_("Can't set this warehouse in different locations with same instance."))

    @api.model
    def import_shopify_locations(self, instance):
        """ Import all the locations from the Shopify instance while confirm the instance connection from odoo.
            :param instance: Record of instance.
            @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 07/11/2019.
            :Task ID: 157407
        """
        instance.connect_in_shopify()
        instance_id = instance.id
        shopify_location_list = []
        try:
            locations = shopify.Location.find()
        except ClientError as error:
            if hasattr(error, "response") and error.response.code == 429 and error.response.msg == "Too Many Requests":
                time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                locations = shopify.Location.find()
        except Exception as error:
            raise UserError(error)
        shop = shopify.Shop.current()
        for location in locations:
            location = location.to_dict()
            vals = self.prepare_vals_for_location(location, instance)
            shopify_location = self.with_context(active_test=False).search(
                [('shopify_location_id', '=', location.get('id')), ('instance_id', '=', instance_id)])
            if shopify_location:
                shopify_location.write(vals)
            else:
                shopify_location = self.create(vals)
            shopify_location_list.append(shopify_location.id)

        self.set_primary_location(shop, instance)

        return shopify_location_list

    def prepare_vals_for_location(self, location, instance):
        """ This method is used to prepare a location vals.
            :param location: Receive response of a location.
            @return: vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 16 October 2020 .
        """
        values = {
            'name':location.get('name'),
            'shopify_location_id':location.get('id'),
            'instance_id':instance.id,
            'legacy':location.get('legacy'),
            'shopify_instance_company_id':instance.shopify_company_id.id,
            "active":location.get('active')
        }
        return values

    def set_primary_location(self, shop, instance):
        """ This method sets the primary location in the Shopify location.
            :param shop: Received response from shopify.
            :param instance: Record of shopify instance.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 16 October 2020 .
        """
        shopify_primary_location = self.search([('is_primary_location', '=', True), ('instance_id', '=', instance.id)],
                                               limit=1)
        if shopify_primary_location:
            shopify_primary_location.write({'is_primary_location':False})

        primary_location_id = shop and shop.to_dict().get('primary_location_id')
        primary_location = self.search(
            [('shopify_location_id', '=', primary_location_id),
             ('instance_id', '=', instance.id)]) if primary_location_id else False
        if primary_location:
            vals = {'is_primary_location':True}
            if not primary_location.export_stock_warehouse_ids:
                vals.update({'export_stock_warehouse_ids':instance.shopify_warehouse_id})
            if not primary_location.import_stock_warehouse_id:
                vals.update({'import_stock_warehouse_id':instance.shopify_warehouse_id})
            primary_location.write(vals)
