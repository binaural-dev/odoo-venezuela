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


class OcapiConnectionConfiguration(models.Model):

    _name = "ocapi.connection.configuration"
    _description = "Ocapi Connection Parameters Configuration"
    #_inherit = "odoo_connector_api.connection"

    name = fields.Char(string="Configuration Name")
    mode = fields.Selection([("production","Production"),("test","Test"),("disabled","Disabled")], string="Configuration Mode")
    seller_user = fields.Many2one("res.users", string="Vendedor", help="Usuario con el que se registrarán las órdenes automáticamente")
    seller_team = fields.Many2one("crm.team", string="Equipo de venta", help="Equipo de ventas para ordenes de venta")

    company_id = fields.Many2one("res.company",string="Company")

    #Import
    import_sales = fields.Boolean(string="Import sales")
    import_sale_start_date = fields.Datetime( string="Sale Date Start" )
    import_payments = fields.Boolean(string="Import Payments")
    import_products = fields.Boolean(string="Import products")
    import_price_list = fields.Boolean(string="Import price list")
    import_stock = fields.Boolean(string="Import stock")
    import_stock_locations = fields.Many2many("stock.warehouse",string="Order Stock Warehouse")
    import_price_lists = fields.Many2many("product.pricelist",relation='ocapi_conf_import_pricelist_rel',column1='configuration_id',column2='pricelist_id',string="Import Price Lists")
    import_sales_action = fields.Selection([ ("quotation_only","Default: Quotation"),
                                            ("payed_confirm_order","Payment confirm order"),
                                            ("payed_confirm_order_shipment","Payment confirm order and shipment"),
                                            ("payed_confirm_order_invoice","Payment confirm order and invoice"),
                                            ("payed_confirm_order_invoice_shipment","Payment confirm order, shipment and invoice")],
                                            string="Action from importing Sale",default="quotation_only")

    #Publish
    publish_products = fields.Boolean(string="Publish products")
    publish_price_list = fields.Boolean(string="Publish price list")
    publish_stock = fields.Boolean(string="Publish stock")
    publish_stock_locations = fields.Many2many("stock.location",string="Publish Stock location")
    publish_price_lists = fields.Many2many("product.pricelist",string="Publish Price Lists")

    #stock warehouse
    #publish location
