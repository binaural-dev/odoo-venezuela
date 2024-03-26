# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from datetime import datetime
from odoo.exceptions import UserError
from odoo import models, fields, api, _


class ProductProduct(models.Model):
    _inherit = "product.product"

    ept_image_ids = fields.One2many('common.product.image.ept', 'product_id', string='Product Images')
    is_drop_ship_product = fields.Boolean(store=False, compute="_compute_is_drop_ship_product")

    @api.depends('route_ids')
    def _compute_is_drop_ship_product(self):
        """ This method is to identify that product is dropship type product and base on this field value it will
        display the vendor stock info in products.
        """
        customer_locations = self.env['stock.location'].search([('usage', '=', 'customer')])
        route_ids = self.route_ids | self.categ_id.route_ids
        stock_rule = self.env['stock.rule'].search([('company_id', '=', self.env.company.id), ('action', '=', 'buy'),
                                                    ('location_dest_id', 'in', customer_locations.ids),
                                                    ('route_id', 'in', route_ids.ids)])
        if stock_rule:
            self.is_drop_ship_product = True
        else:
            self.is_drop_ship_product = False

    def prepare_common_image_vals(self, vals):
        """
        Prepares vals for creating common product image record.
        @param vals: Vals having image data.
        @param product: Record of Product.
        @return:Dictionary
        """
        image_vals = {"sequence": 0,
                      "image": vals.get("image_1920", False),
                      "name": self.name,
                      "product_id": self.id,
                      "template_id": self.product_tmpl_id.id}
        return image_vals

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherited for adding the main image in common images.
        """
        res = super(ProductProduct, self).create(vals_list)
        for vals in vals_list:
            if vals.get("image_1920", False) and res:
                image_vals = res.prepare_common_image_vals(vals)
                self.env["common.product.image.ept"].create(image_vals)
        return res

    def write(self, vals):
        """
        Inherited for adding the main image in common images.
        """
        res = super(ProductProduct, self).write(vals)
        if vals.get("image_1920", False) and self:
            common_product_image_obj = self.env["common.product.image.ept"]
            for record in self:
                if vals.get("image_1920"):
                    image_vals = record.prepare_common_image_vals(vals)
                    common_product_image_obj.create(image_vals)

        return res

    def get_products_based_on_movement_date_ept(self, from_datetime, company):
        """ This method is used to get product records which stock movement updates after from date.
            @param from_datetime: Date
            @param company: Company
            @return company: It will return list of product records
        """
        if not from_datetime or not company:
            raise UserError(_('You must provide the From Date and Company'))
        result = []
        mrp_module = self.search_installed_module_ept('mrp')
        date = str(datetime.strftime(from_datetime, '%Y-%m-%d %H:%M:%S'))

        if mrp_module:
            result = self.get_product_movement_of_bom_product(date, company)

        qry = ("""select distinct product_id from stock_move where write_date >= '%s' and company_id = %d and
                 state in ('partially_available','assigned','done','cancel')""" % (date, company.id))
        self._cr.execute(qry)
        result += self._cr.dictfetchall()
        product_ids = [product_id.get('product_id') for product_id in result]

        return list(set(product_ids))

    def search_installed_module_ept(self, module_name):
        """ This method is used to check the module is install or not.
            @param module_name: Name of Module
            @return: Record of module
        """
        module_obj = self.env['ir.module.module']
        module = module_obj.sudo().search([('name', '=', module_name), ('state', '=', 'installed')])
        return module

    def get_product_movement_of_bom_product(self, date, company):
        """ This method is used to get BOM type of product which stock movement updates after specific date.
            @param: date : String formate of date and time.
            @param: company : Record of company.
        """
        mrp_qry = ("""select distinct p.id as product_id from product_product as p
                    inner join mrp_bom as mb on mb.product_tmpl_id=p.product_tmpl_id
                    inner join mrp_bom_line as ml on ml.bom_id=mb.id
                    inner join stock_move as sm on sm.product_id=ml.product_id
                    where sm.write_date >= '%s' and sm.company_id = %d and sm.state in 
                    ('partially_available','assigned','done','cancel')""" % (date, company.id))
        self._cr.execute(mrp_qry)
        result = self._cr.dictfetchall()
        return result

    def prepare_location_and_product_ids(self, warehouse, product_list):
        """
        This method prepares location and product ids from warehouse and list of product id.
        @param warehouse: Record of Warehouse
        @param product_list: Ids of Product.
        @return: Ids of locations and products in string.
        """
        locations = self.env['stock.location'].search([('location_id', 'child_of', warehouse.lot_stock_id.ids)])
        location_ids = ','.join(str(e) for e in locations.ids)
        product_ids = ','.join(str(e) for e in product_list)
        return location_ids, product_ids

    def check_for_bom_products(self, product_ids):
        """
        This method checks if any product is BoM, then get stock for them.
        @param product_ids: Ids of Product.
        @return: Ids of BoM products.
        """
        bom_product_ids = []
        mrp_module = self.search_installed_module_ept('mrp')
        if mrp_module:
            qry = ("""select p.id as product_id from product_product as p
                        inner join mrp_bom as mb on mb.product_tmpl_id=p.product_tmpl_id
                        and p.id in (%s)""" % product_ids)
            self._cr.execute(qry)
            bom_product_ids = self._cr.dictfetchall()
            bom_product_ids = [product_id.get('product_id') for product_id in bom_product_ids]

        return bom_product_ids

    def prepare_free_qty_query(self, location_ids, simple_product_list_ids):
        """
        This method prepares query for fetching the free qty.
        @param location_ids:Ids of Locations.
        @param simple_product_list_ids: Ids of products which are not BoM.
        @return: Prepared query in string.
        """
        query = """select pp.id as product_id,
                COALESCE(sum(sq.quantity)-sum(sq.reserved_quantity),0) as stock
                from product_product pp
                left join stock_quant sq on pp.id = sq.product_id and sq.location_id in (%s)
                where pp.id in (%s) group by pp.id;""" % (location_ids, simple_product_list_ids)
        return query

    def prepare_onhand_qty_query(self, location_ids, simple_product_list_ids):
        """
        This method prepares query for fetching the On hand qty.
        @param location_ids:Ids of Locations.
        @param simple_product_list_ids: Ids of products which are not BoM.
        """
        query = """select pp.id as product_id,
                COALESCE(sum(sq.quantity),0) as stock
                from product_product pp
                left join stock_quant sq on pp.id = sq.product_id and sq.location_id in (%s)
                where pp.id in (%s) group by pp.id;""" % (location_ids, simple_product_list_ids)
        return query

    def prepare_forecasted_qty_query(self, location_ids, simple_product_list_ids):
        """
        This method prepares query for fetching the forecasted qty.
        @param location_ids:Ids of Locations.
        @param simple_product_list_ids: Ids of products which are not BoM.
        @return: Prepared query in string.
        """
        query = ("""select product_id,sum(stock) as stock from (select pp.id as product_id,
                COALESCE(sum(sq.quantity)-sum(sq.reserved_quantity),0) as stock
                from product_product pp
                left join stock_quant sq on pp.id = sq.product_id and sq.location_id in (%s)
                where pp.id in (%s) group by pp.id
                union all
                select product_id as product_id, sum(product_qty) as stock from stock_move
                where state in ('assigned') and product_id in (%s) and location_dest_id in (%s)
                group by product_id) as test group by test.product_id""" % (location_ids, simple_product_list_ids,
                                                                            simple_product_list_ids, location_ids))
        return query

    def get_free_qty_ept(self, warehouse, product_list):
        """ This method is used to get free to use quantity based on warehouse and products.
            @param warehouse: Records of warehouse
            @param product_list: List of product ids
            @return: Dictionary with a product and its quantity.
        """
        qty_on_hand = {}
        location_ids, product_ids = self.prepare_location_and_product_ids(warehouse, product_list)

        bom_product_ids = self.check_for_bom_products(product_ids)
        if bom_product_ids:
            # Passed location instead of the warehouse in with_context, because it was doing export the product stock
            # of all locations of the warehouse instead of the stock location of the warehouse.
            bom_products = self.with_context(location=[int(location) for location in location_ids.split(',')]).browse(
                bom_product_ids)
            for product in bom_products:
                actual_stock = getattr(product, 'free_qty')
                qty_on_hand.update({product.id: actual_stock})

        simple_product_list = list(set(product_list) - set(bom_product_ids))
        simple_product_list_ids = ','.join(str(e) for e in simple_product_list)
        if simple_product_list_ids:
            qry = self.prepare_free_qty_query(location_ids, simple_product_list_ids)
            self._cr.execute(qry)
            result = self._cr.dictfetchall()
            for i in result:
                qty_on_hand.update({i.get('product_id'): i.get('stock')})
        return qty_on_hand

    def prepare_forecasted_qty_query_for_bom_product(self, location_ids, product_ids):
        query = (("""select product_id, free_qty+incoming_qty-outgoing_qty stock from (
            select sq.product_id, COALESCE(sum(sq.quantity)-sum(sq.reserved_quantity),0) free_qty,
            COALESCE(sum(sm_in.product_qty),0) incoming_qty,COALESCE(sum(sm_out.product_qty),0) outgoing_qty 
            from 
            stock_quant sq 
            left join stock_move sm_in on sm_in.product_id= sq.product_id and (sm_in.location_id in (%s) or sm_in.location_dest_id in (%s))
                                          and sm_in.state in ('waiting', 'confirmed', 'assigned', 'partially_available')
            left join stock_move sm_out on sm_out.product_id= sq.product_id and (sm_out.location_dest_id in (%s) or sm_out.location_id in (%s))
                                          and sm_out.state in ('waiting', 'confirmed', 'assigned', 'partially_available')
            where sq.product_id in (%s) and 
                  sq.location_id in (%s) group by sq.product_id) as test;""" % (
            location_ids, location_ids, location_ids, location_ids, product_ids, location_ids)))
        return query

    def get_forecasted_qty_ept(self, warehouse, product_list):
        """ This method is used to get forecast quantity based on warehouse and products.
            @param warehouse: Records of warehouse
            @param product_list: List of product ids
            @return: Dictionary with a product and its quantity.
        """
        forcasted_qty = {}
        location_ids, product_ids = self.prepare_location_and_product_ids(warehouse, product_list)

        bom_product_ids = self.check_for_bom_products(product_ids)
        # bom_product_list_ids = ','.join(str(e) for e in bom_product_ids)
        # if bom_product_list_ids:
        #     qry = self.prepare_forecasted_qty_query_for_bom_product(location_ids, bom_product_list_ids)
        #     self._cr.execute(qry)
        #     actual_stock = self._cr.dictfetchall()
        #     for i in actual_stock:
        #         forcasted_qty.update({i.get('product_id'): i.get('stock')})
        if bom_product_ids:
            bom_products = self.with_context(warehouse=warehouse.ids).browse(bom_product_ids)
            for product in bom_products:
                actual_stock = getattr(product, 'free_qty') + getattr(product, 'incoming_qty') - getattr(product,
                                                                                                         'outgoing_qty')
                forcasted_qty.update({product.id: actual_stock})

        simple_product_list = list(set(product_list) - set(bom_product_ids))
        simple_product_list_ids = ','.join(str(e) for e in simple_product_list)
        if simple_product_list_ids:
            qry = self.prepare_forecasted_qty_query(location_ids, simple_product_list_ids)
            self._cr.execute(qry)
            result = self._cr.dictfetchall()
            for i in result:
                forcasted_qty.update({i.get('product_id'): i.get('stock')})
        return forcasted_qty

    def get_onhand_qty_ept(self, warehouse, product_list):
        """
        This method is return On Hand quantity based on warehouse and product list
        :param warehouse:warehouse object
        :param product_list:list of product_ids (Not browsable records)
        :return: On hand Quantity
        """
        onhand_qty = {}
        location_ids, product_ids = self.prepare_location_and_product_ids(warehouse, product_list)

        bom_product_ids = self.check_for_bom_products(product_ids)
        if bom_product_ids:
            bom_products = self.with_context(warehouse=warehouse.ids).browse(bom_product_ids)
            for product in bom_products:
                actual_stock = getattr(product, 'qty_available')
                onhand_qty.update({product.id: actual_stock})

        simple_product_list = list(set(product_list) - set(bom_product_ids))
        simple_product_list_ids = ','.join(str(e) for e in simple_product_list)
        if simple_product_list_ids:
            qry = self.prepare_onhand_qty_query(location_ids, simple_product_list_ids)
            self._cr.execute(qry)
            result = self._cr.dictfetchall()
            for i in result:
                onhand_qty.update({i.get('product_id'): i.get('stock')})
        return onhand_qty

    def _prepare_out_svl_vals(self, quantity, company):
        """
        This method is used if MRP installed, BOM type is Manufacturing
        and While processing shipped order workflow via Webhook. Then it
        will process workflow with OdooBot User not public user.
        @error: Receive error while process auto invoice workflow,
        Error is:(You are not allowed to access 'Bill of Material' (mrp.bom) records.
        """
        if 'is_connector' in self._context and self._context.get('is_connector'):
            self = self.with_user(1)
        return super(ProductProduct, self)._prepare_out_svl_vals(quantity, company)
