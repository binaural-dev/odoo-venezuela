# -*- coding: utf-8 -*-

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
#from .warning import warning
import requests

class OcapiConnectionBindingSaleOrderPayment(models.Model):

    _name = "ocapi.binding.payment"
    _description = "Ocapi Sale Order Payment Binding"
    _inherit = "ocapi.connection.binding"

    name = fields.Char(string="Payment Name")
    account_payment_id = fields.Many2one("account.payment",string="Payment")

    _sql_constraints = [
        ('unique_conn_id_payment', 'unique(connection_account,conn_id,conn_variation_id,account_payment_id)', 'Binding exists for this item: payment!')
    ]

class OcapiConnectionBindingSaleOrderShipmentItem(models.Model):

    _name = "ocapi.binding.shipment.item"
    _description = "Ocapi Sale Order Shipment Item"
    _inherit = "ocapi.connection.binding"

    name = fields.Char(string="Shipment Product Item")
    shipping_id = fields.Many2one("ocapi.binding.shipment",string="Shipment")

    _sql_constraints = [
        ('unique_conn_id_shipment_item', 'unique(connection_account,conn_id,shipping_id)', 'Binding exists for this item: shipment.item!')
    ]

class OcapiConnectionBindingSaleOrderShipment(models.Model):

    _name = "ocapi.binding.shipment"
    _description = "Ocapi Sale Order Shipment Binding"
    _inherit = "ocapi.connection.binding"

    name = fields.Char(string="Shipment Name")

    order_id = fields.Many2one("ocapi.binding.sale_order",string="Order")
    products = fields.One2many("ocapi.binding.shipment.item", "shipping_id", string="Product Items")

    _sql_constraints = [
        ('unique_conn_id_shipment', 'unique(connection_account,conn_id,order_id)', 'Binding exists for this item: shipment!')
    ]

class OcapiConnectionBindingSaleOrderClient(models.Model):

    _name = "ocapi.binding.client"
    _description = "Ocapi Sale Order Client Binding"
    _inherit = "ocapi.connection.binding"

    name = fields.Char(string="Client Name")
    partner_id = fields.Many2one("res.partner",string="Partner")

    _sql_constraints = [
        ('unique_conn_id_res_partner', 'unique(connection_account,conn_id,conn_variation_id,partner_id)', 'Binding exists for this item: client!')
    ]

class OcapiConnectionBindingSaleOrderLine(models.Model):

    _name = "ocapi.binding.sale_order_line"
    _description = "Ocapi Sale Order Line Binding"
    _inherit = "ocapi.connection.binding"

    name = fields.Char(string="Order Line Name")

    #odoo order line
    sale_order_line = fields.Many2one("sale.order.line",string="Order Line")

    _sql_constraints = [
        ('unique_conn_id_sale_order_line', 'unique(connection_account,conn_id,conn_variation_id,sale_order_line)', 'Binding exists for this item: sale_order_line!')
    ]

class OcapiConnectionBindingSaleOrder(models.Model):

    _name = "ocapi.binding.sale_order"
    _description = "Ocapi Sale Order Binding"
    _inherit = "ocapi.connection.binding"

    name = fields.Char(string="Connector Order Name",index=True)
    state = fields.Selection( selection=[
        #Initial state of an order, and it has no payment yet.
                                        ("confirmed","Confirmado"),
        #The order needs a payment to become confirmed and show users information.
                                      ("payment_required","Pago requerido"),
        #There is a payment related with the order, but it has not been accredited yet
                                    ("payment_in_process","Pago en proceso"),
        #The order has a related payment and it has been accredited.
                                    ("paid","Pagado"),
        #The order has a been paid and delivered to the customer
                                    ("delivered","Entregado"),
        #The order has not completed by some reason.
                                    ("cancelled","Cancelado"),
        #The order has a been cancelled and refunded
                                            ("refunded","Reembolsado"),
        #The order has a been cancelled and returned
                                            ("returned","Devuelto")]
        , string='Order State')
    sale_order = fields.Many2one("sale.order",string="Sale Order")

    date_created = fields.Datetime(string="Date Created",index=True)
    date_closed = fields.Datetime(string='Closing Date',index=True)

    client = fields.Many2one("ocapi.binding.client",string="Client",index=True)
    lines = fields.Many2many("ocapi.binding.sale_order_line",string="Order Items")
    payments = fields.Many2many("ocapi.binding.payment",string="Order Payments")
    shipments = fields.Many2many("ocapi.binding.shipment",string="Order Shipments")

    _sql_constraints = [
        ('unique_conn_id_sale_order', 'unique(connection_account,conn_id,conn_variation_id,sale_order)', 'Binding exists for this item: sale_order!')
    ]
