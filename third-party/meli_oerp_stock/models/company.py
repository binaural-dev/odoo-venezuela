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

class ResCompany(models.Model):

    _inherit = "res.company"

    mercadolibre_stock_warehouse = fields.Many2one("stock.warehouse", string="Stock Warehouse Default", help="Almacen predeterminado")
    mercadolibre_stock_location_to_post = fields.Many2one("stock.location", string="Stock Location To Post", help="Ubicación desde dónde publicar el stock")
    mercadolibre_stock_location_to_post_many = fields.Many2many("stock.location", string="Stock Locations To Post", help="Ubicaciones desde dónde publicar el stock")

    mercadolibre_stock_warehouse_full = fields.Many2one("stock.warehouse", string="Stock Warehouse Default for FULL", help="Almacen predeterminado para modo fulfillment")
    mercadolibre_stock_location_to_post_full = fields.Many2one("stock.location", string="Stock Location To Post for Full", help="Ubicación desde dónde publicar el stock en modo Full")

    mercadolibre_order_confirmation_delivery = fields.Selection([ ("manual", "No entregar"),
                                                ("paid_confirm_deliver", "Pagado > Entregar"),
                                                ("paid_confirm_shipped_deliver", "Pagado > Entregado > Entregar")],
                                                string='Acción sobre la entrega al confirmar un pedido',
                                                help='Acción sobre la entrega al confirmar una orden o pedido de venta')

    mercadolibre_order_confirmation_delivery_full = fields.Selection([ ("manual", "No entregar"),
                                                ("paid_confirm_deliver", "Pagado > Entregar"),
                                                ("paid_confirm_shipped_deliver", "Pagado > Entregado > Entregar")],
                                                string='(FULL) Acción sobre la entrega al confirmar un pedido',
                                                help='(FULL) Acción sobre la entrega al confirmar una orden o pedido de venta')

    #TODO: process
    mercadolibre_cron_get_shipments = fields.Boolean(string='Force shipment validation',help='Force shipment validation')
    mercadolibre_stock_filter_order_datetime = fields.Datetime("Order Closed Date (Forcing shipment validation)")
    mercadolibre_stock_filter_order_datetime_to = fields.Datetime("Order Closed Date To (Forcing shipment validation)")

    mercadolibre_stock_virtual_available = fields.Selection(string="Cantidad disponible",
                                                            selection=[
                                                                        ("virtual","Planificado (virtual_available)"),
                                                                        ("theoretical","En mano (quantity)"),
                                                                        ("qty_reserved","Cantidad menos reservado (quantity - reserved)")
                                                            ],
                                                            default='virtual')

    mercadolibre_stock_location_operation = fields.Selection( string="Operación sobre las ubicaciones",
                                                              selection=[
                                                                            ("sum","Suma de las ubicaciones"),
                                                                            ("maximum","Maximo"),
                                                                            #("minimum","Minimo")
                                                              ],
                                                              default='sum',
                                                              help="Suma, maximo o minimo como operacion de las diferentes ubicaciones activas para MercadoLibre")

    #TODO: check if 3rd option needed to force quantity - reserved mercadolibre_stock_virtual_available = fields.Selection([("virtual","Virtual Available"),("virtual_reserved","Virtual ( on hand - reserved )"),("theoretical","En mano (quantity)")],default='virtual')

    #TODO: activate
    #mercadolibre_stock_sku_regex = fields.Char(string="Sku Regex")

    #TODO: activate
    mercadolibre_stock_sku_mapping = fields.Many2many("meli_oerp.sku.rule",string="Sku Rules")

    #TODO:
    #si shipped que haga automaticamente ejecute la entrega
    #mercadolibre_shipped = fields.Boolean()

    #procesar cuando es "Comprar"
    #mercadolibre_stock_sale_route_process = fields.Boolean(string="Routing Sale")

    mercadolibre_stock_website_sale = fields.Boolean(string="Use Meli Stock for Ecommerce",default=False)

    def cron_meli_shipments( self ):

        _logger.info('company cron_meli_shipments() '+str(self))

        company = self.env.user.company_id

        apistate = self.env['meli.util'].get_new_instance(company)
        if apistate.needlogin_state:
            return True

        _logger.info(str(company.name))
        condition = company.mercadolibre_cron_get_shipments or (company.mercadolibre_stock_filter_order_datetime or company.mercadolibre_stock_filter_order_datetime_to)
        if (condition):
            _logger.info("company.mercadolibre_cron_get_shipments")
            self.meli_query_get_shipments( meli=apistate, config=company)

    def meli_query_get_shipments( self, meli=None, config=None ):

        _logger.info("meli_query_get_shipments")
        #recorrer ordenes y procesar entregas en funcion de los valores de
        # mercadolibre_order_confirmation_delivery
        # mercadolibre_order_confirmation_delivery_full
        # mercadolibre_stock_filter_order_datetime
        # mercadolibre_stock_filter_order_datetime_to
        start_date = ( config.mercadolibre_stock_filter_order_datetime and [('date_closed','>=',''+str(config.mercadolibre_stock_filter_order_datetime) )]) or []
        end_date = ( config.mercadolibre_stock_filter_order_datetime_to and [('date_closed','<=',''+str(config.mercadolibre_stock_filter_order_datetime_to) )]) or []
        orders_in_range = self.env["mercadolibre.orders"].search( start_date + end_date )
        _logger.info("orders_in_range:"+str(orders_in_range)+" start_date:"+str(start_date)+" end_date:"+str(end_date))
        if orders_in_range and start_date and end_date:
            for morder in orders_in_range:
                so = morder.sale_order
                if so:
                    so.confirm_ml_stock( meli=meli, config=config, force=True )
