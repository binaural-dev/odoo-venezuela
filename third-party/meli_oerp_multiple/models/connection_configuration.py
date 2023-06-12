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

class MercadoLibreChannel(models.Model):

    _name = 'mercadolibre.channel'
    _description = 'MercadoLibre Channel'

    name = fields.Char(string="Name",required=True,index=True)
    code = fields.Char(string="Code",help="Code Prefix for Orders: (ML for MercadoLibre) SHO (Shopify)")
    app_id = fields.Char(string="App Id",required=True,index=True)
    country_id = fields.Many2one("res.country",string="Country",index=True)
    journal_id = fields.Many2one( "account.journal", string="Journal")
    partner_id = fields.Many2one( "res.partner", string="Partner")
    #sequence_id = fields.Many2one('ir.sequence', string='Order Sequence',
    #    help="Order labelling for this channel", copy=False)


class MercadoLibreConnectionConfiguration(models.Model):

    _name = "mercadolibre.configuration"
    _description = "MercadoLibre Connection Parameters Configuration"
    _inherit = "ocapi.connection.configuration"

    #mercadolibre_channels = fields.Many2many("mercadolibre.channel", string="MercadoLibre Channels")
    accounts = fields.One2many( "mercadolibre.account","configuration", string="Accounts", help="Accounts"  )

    #Import #extending because of relational table name conflicts, conflict with publish price list (TODO: let one)
    import_price_lists = fields.Many2many("product.pricelist",relation='mercadolibre_conf_import_pricelist_rel',column1='configuration_id',column2='pricelist_id',string="Import Price Lists")


    mercadolibre_category_import = fields.Char( string='Category to import', help='Category Code to Import, check Recursive Import to import the full tree', size=256)
    mercadolibre_recursive_import = fields.Boolean( string='Recursive import', help='Import all the category tree from Category Code')

    mercadolibre_cron_refresh = fields.Boolean(string='Keep alive',help='Cron Automatic Token Refresh for keeping ML connection alive.')
    mercadolibre_cron_mail = fields.Many2one(
        comodel_name="mail.template",
        string="Error E-mail Template",
        help="Select the email template that will be sent when "
        "cron refresh fails.")
    mercadolibre_cron_get_orders = fields.Boolean(string="Importar pedidos",help='Cron Get Orders / Pedidos de venta')
    mercadolibre_cron_get_orders_shipment = fields.Boolean(string='Importar envíos',help='Cron Get Orders Shipment')
    mercadolibre_cron_get_orders_shipment_client = fields.Boolean(string='Importar clientes',help='Cron Get Orders Shipment Client')
    mercadolibre_cron_get_questions = fields.Boolean(string='Importar preguntas',help='Cron Get Questions')
    mercadolibre_cron_get_update_products = fields.Boolean(string='Actualizar productos en Odoo',help='Cron Update Products already imported')
    mercadolibre_cron_post_update_products = fields.Boolean(string='Actualizar productos en ML',help='Cron Update Posted Products, Product Templates or Variants with Meli Publication field checked')
    mercadolibre_cron_post_update_stock = fields.Boolean(string='Publicar Stock',help='Cron Post Updated Stock')
    mercadolibre_cron_post_update_price = fields.Boolean(string='Publicar Precio',help='Cron Post Updated Price')
    mercadolibre_create_website_categories = fields.Boolean(string='Crear categorías',help='Create Website eCommerce Categories from imported products ML categories')
    mercadolibre_pricelist = fields.Many2one( "product.pricelist", "Product Pricelist default", help="Select price list for ML product"
        "when published from Odoo to ML")
    mercadolibre_pricelist_usd = fields.Many2one( "product.pricelist", "Product Pricelist default USD", help="USD Select price list for ML product"
        "when published from Odoo to ML")

    mercadolibre_order_total_config = fields.Selection( [('manual','Manual'),('manual_conflict','Manual conflict'),('paid_amount','Paid Amount'),('total_amount','Total Amount')] , string="Total Config.", help='Order Total Config, stategy to calculate order/invoice total amount.' )


    mercadolibre_buying_mode = fields.Selection( [("buy_it_now","Compre ahora"),
                                                  ("classified","Clasificado")],
                                                  string='Método de compra predeterminado')
    mercadolibre_currency = fields.Selection([  ("ARS","Peso Argentino (ARS)"),
                                                ("MXN","Peso Mexicano (MXN)"),
                                                ("COP","Peso Colombiano (COP)"),
                                                ("PEN","Sol Peruano (PEN)"),
                                                ("BOB","Boliviano (BOB)"),
                                                ("BRL","Real (BRL)"),
                                                ("CLP","Peso Chileno (CLP)"),
                                                ("CRC","Colon Costarricense (CRC)"),
                                                ("UYU","Peso Uruguayo (UYU)"),
                                                ("VES","Bolivar Soberano (VES)"),
                                                ("USD","Dolar Estadounidense (USD)")],
                                                string='Moneda predeterminada')
    mercadolibre_condition = fields.Selection([ ("new", "Nuevo"),
                                                ("used", "Usado"),
                                                ("not_specified","No especificado")],
                                                string='Condición',
                                                help='Condición del producto predeterminado')
    mercadolibre_warranty = fields.Char(string='Garantía', size=256, help='Garantía del producto predeterminado. Es obligatorio y debe ser un número seguido por una unidad temporal. Ej. 2 meses, 3 años.')
    mercadolibre_listing_type = fields.Selection([("free","Libre"),
                                                ("bronze","Bronce/Clásica-(UY)"),
                                                ("silver","Plata"),
                                                ("gold","Oro"),
                                                ("gold_premium","Gold Premium/Oro Premium"),
                                                ("gold_special","Gold Special/Clásica/Premium-(UY)"),
                                                ("gold_pro","Oro Pro")],
                                                string='Tipo de lista',
                                                help='Tipo de lista  predeterminada para todos los productos')
    mercadolibre_attributes = fields.Boolean(string='Apply product attributes')
    mercadolibre_exclude_attributes = fields.Many2many('product.attribute.value',
        string='Valores excluidos', help='Seleccionar valores que serán excluidos para las publicaciones de variantes')
    mercadolibre_update_local_stock = fields.Boolean(string='Cron Get Products and take Stock from ML')
    mercadolibre_product_template_override_variant = fields.Boolean(string='Product template override Variant')
    mercadolibre_product_template_override_method = fields.Selection(string='Método para Sobreescribir',
                                                                    help='Método para Sobreescribir Titulo y Descripcion desde la información del Producto a la solapa de ML y sus variantes de ML',
                                                                    selection=[
                                                                        ('default','Predeterminado, sobreescribe descripcion solamente'),
                                                                        ('description','Sobreescribir descripcion solamente'),
                                                                        ('title','Sobreescribir título solamente'),
                                                                        ('title_and_description','Sobreescribir titulo y descripcion')
                                                                    ],
                                                                    default='default')
    mercadolibre_order_confirmation = fields.Selection([ ("manual", "Manual"),
                                                ("paid_confirm", "Pagado>Confirmado"),
                                                ("paid_delivered", "Pagado>Entregado"),
                                                ("paid_confirm_with_invoice", "Pagado>Facturado"),
                                                ("paid_delivered_with_invoice", "Pagado>Facturado y Entregado")],
                                                default='manual',
                                                string='Acción al recibir un pedido',
                                                help='Acción al confirmar una orden o pedido de venta')
    mercadolibre_order_confirmation_full = fields.Selection([ ("manual", "Manual"),
                                                ("paid_confirm", "Pagado>Confirmado"),
                                                ("paid_delivered", "Pagado>Entregado"),
                                                ("paid_confirm_with_invoice", "Pagado>Facturado"),
                                                ("paid_delivered_with_invoice", "Pagado>Facturado y Entregado")],
                                                default='manual',
                                                string='Acción al recibir un pedido en FULL',
                                                help='Acción al confirmar una orden o pedido de venta en FULL')
    mercadolibre_product_attribute_creation = fields.Selection([ ("manual", "Manual"),
                                                ("full", "Sincronizado completo (uno a uno, sin importar si se usa o no)"),
                                                ("dynamic", "Dinámico (cuando se asocia un producto a una categoría (ML) con atributos (ML))") ],
                                                default='manual',
                                                string='Create Product Attributes')
    #'mercadolibre_login': fields.selection( [ ("unknown", "Desconocida"), ("logged","Abierta"), ("not logged","Cerrada")],string='Estado de la sesión'), )
    mercadolibre_overwrite_template = fields.Boolean(string='Overwrite product template',help='Sobreescribir siempre Nombre y Descripción de la plantilla.')
    mercadolibre_overwrite_variant = fields.Boolean(string='Overwrite product variant',help='Sobreescribir siempre Nombre y Descripción de la variante.')
    mercadolibre_process_notifications = fields.Boolean(string='Process all notifications',help='Procesar las notificaciones recibidas (/meli_notify)')

    mercadolibre_create_product_from_order = fields.Boolean(string='Importar productos inexistentes',help='Importar productos desde la orden si no se encuentran en la base.')
    mercadolibre_update_existings_variants = fields.Boolean(string='Actualiza/agrega variantes',help='Permite agregar y actualizar variantes de un producto existente (No recomendable cuando se está ya en modo Odoo a ML, solo usar cuando se importa por primera vez de ML a Odoo, para no romper el stock)')
    mercadolibre_tax_included = fields.Selection( string='Tax Included',
                                                  help='Esto se aplica al importar ordenes, productos y tambien al publicar, sobre la lista de precio seleccionada o sobre el precio de lista.',
                                                  selection=[ ('auto','Configuración del sistema'),
                                                              ('tax_included','Impuestos ya incluídos del precio de lista'),
                                                              ('tax_excluded','Impuestos excluídos del precio de lista') ] )

    mercadolibre_do_not_use_first_image = fields.Boolean(string="Do not use first image")
    mercadolibre_cron_post_new_products = fields.Boolean(string='Incluir nuevos productos',help='Cron Post New Products, Product Templates or Variants with Meli Publication field checked')
    mercadolibre_cron_get_new_products = fields.Boolean(string='Importar nuevos productos',help='Cron Import New Products, Product Templates or Variants')

    mercadolibre_process_offset = fields.Char('Offset for pause all')
    mercadolibre_post_default_code = fields.Boolean(string='Post SKU',help='Post Odoo default_code field for templates or variants to seller_custom_field in ML')
    mercadolibre_import_search_sku = fields.Boolean(string='Search SKU',help='Search product by default_code')

    mercadolibre_seller_user = fields.Many2one("res.users", string="Vendedor ML", help="Usuario con el que se registrarán las órdenes automáticamente")
    mercadolibre_seller_team = fields.Many2one("crm.team", string="Equipo de ventas ML", help="Equipo de ventas asociado a las ventas de ML")
    mercadolibre_remove_unsync_images = fields.Boolean(string='Removing unsync images (ml id defined for image but no longer in ML publication)')

    mercadolibre_official_store_id = fields.Char(string="Official Store Id")

    mercadolibre_payment_term = fields.Many2one("account.payment.term",string="Payment Term")

    ## STOCK Configuration

    mercadolibre_stock_warehouse = fields.Many2one("stock.warehouse", string="Stock Warehouse Default", help="Almacen predeterminado")
    mercadolibre_stock_location_to_post = fields.Many2one("stock.location", string="Stock Location To Post", help="Ubicación desde dónde publicar el stock")
    #mercadolibre_stock_location_to_post_many = fields.Many2many("stock.location", string="Stock Location To Post", help="Ubicaciones desde dónde publicar el stock")

    mercadolibre_stock_warehouse_full = fields.Many2one("stock.warehouse", string="Stock Warehouse Default for FULL", help="Almacen predeterminado para modo fulfillment")
    mercadolibre_stock_location_to_post_full = fields.Many2one("stock.location", string="Stock Location To Post for Full", help="Ubicación desde dónde publicar el stock en modo Full")

    mercadolibre_order_confirmation_delivery = fields.Selection([ ("manual", "No entregar"),
                                                ("paid_confirm_deliver", "Pagado > Entregar"),
                                                ("paid_confirm_shipped_deliver", "Pagado > Entregado > Entregar")],
                                                string='Acción de la entrega al confirmar un pedido',
                                                help='Acción de la entrega al confirmar una orden o pedido de venta')

    mercadolibre_order_confirmation_delivery_full = fields.Selection([ ("manual", "No entregar"),
                                                ("paid_confirm_deliver", "Pagado > Entregar"),
                                                ("paid_confirm_shipped_deliver", "Pagado > Entregado > Entregar")],
                                                string='(FULL) Acción de la entrega al confirmar un pedido',
                                                help='(FULL) Acción de la entrega al confirmar una orden o pedido de venta')

    #TODO: process shippings
    mercadolibre_stock_filter_order_datetime = fields.Datetime("Order Closed Date (For shipping)")
    mercadolibre_stock_filter_order_datetime_to = fields.Datetime("Order Closed Date To (For shipping)")


    #TODO: activate
    mercadolibre_stock_virtual_available = fields.Selection([("virtual","Virtual (quantity-reserved)"),("theoretical","En mano (quantity)")],default='virtual')

    mercadolibre_stock_sku_mapping = fields.Many2many("meli_oerp.sku.rule",string="Sku Rules")




    ## ACCOUNT configuration

    mercadolibre_process_payments_customer = fields.Boolean(string="Process payments from Customer")
    mercadolibre_process_payments_supplier_fea = fields.Boolean(string="Process payments fea to Supplier ML")
    mercadolibre_process_payments_supplier_shipment = fields.Boolean(string="Process payments shipping list cost to Supplier ML")

    mercadolibre_process_payments_journal = fields.Many2one("account.journal",string="Account Journal for MercadoLibre")
    mercadolibre_process_payments_res_partner = fields.Many2one("res.partner",string="MercadoLibre Partner")

    mercadolibre_order_confirmation_hook = fields.Char(string="Order Hook",help="https://www.hookserver.com/app")
    mercadolibre_product_confirmation_hook = fields.Char(string="Product Hook",help="https://www.hookserver.com/app")

    mercadolibre_filter_order_datetime_start = fields.Datetime("Start Order Closed Date",help="Fecha a partir de la cual no se bloquean las entradas de pedidos desde ML")
    #mercadolibre_filter_order_cron_max = fields.Integer(string="Cantidad de ordenes maximas a chequear por iteracion de cron")
    mercadolibre_filter_order_datetime = fields.Datetime("Order Closed Date From",help="Fecha inicial para la importacion de pedidos (vacio: ultimas 50)")
    mercadolibre_filter_order_datetime_to = fields.Datetime("Order Closed Date To",help="Fecha final para la importacion de pedidos (vacio: el dia de hoy)")

    mercadolibre_order_confirmation_invoice = fields.Selection([ ("manual", "No facturar"),
                                                ("paid_confirm_invoice", "Pagado > Facturar"),
                                                ("paid_confirm_draft_invoice", "Pagado > Facturar borrador"),
                                                ("paid_confirm_delivered_invoice", "Entregado > Facturar"),
                                                #("paid_confirm_invoice_deliver", "Pagado > Facturar > Entregar")
                                                ],
                                                string='Acción al confirmar un pedido',
                                                help='Acción al confirmar una orden o pedido de venta')

    mercadolibre_order_confirmation_invoice_full = fields.Selection([ ("manual", "No facturar"),
                                                ("paid_confirm_invoice", "Pagado > Facturar"),
                                                ("paid_confirm_draft_invoice", "Pagado > Facturar borrador"),
                                                ("paid_confirm_delivered_invoice", "Entregado > Facturar"),
                                                #("paid_confirm_invoice_deliver", "Pagado > Facturar > Entregar")
                                                ],
                                                string='(FULL) Acción al confirmar un pedido',
                                                help='(FULL) Acción al confirmar una orden o pedido de venta')

    mercadolibre_post_invoice = fields.Boolean(string="Post Invoice Automatic",help="Try to post invoice, when order is revisited or refreshed.")
    mercadolibre_post_invoice_dont_send = fields.Boolean(string="Dont really send, just prepare to post invoice.")

    mercadolibre_invoice_journal_id = fields.Many2one( "account.journal", string="Diario Facturacion" )
    mercadolibre_invoice_journal_id_full = fields.Many2one( "account.journal", string="Diario Facturacion Full" )

    #mercadolibre_account_payment_receiptbook_id = fields.Many2one( "account.payment.receiptbook", string="Recibos")
    #mercadolibre_account_payment_supplier_receiptbook_id = fields.Many2one( "account.payment.receiptbook", string="Orden de pago")

    def copy_from_company( self, context=None, company=None ):
        context = context or self.env.context
        company = company or (self.accounts and self.accounts[0].company_id) or self.env.user.company_id
        _logger.info("Copy configuration from company: "+str(context)+" company:" +str(company))
        if company:
            #self.import_price_lists = company.
            for field in self._fields:
                if "mercadolibre_" in field and field in company._fields:
                    _logger.info("copy field: " + str(field)+" value: "+str(self[field]) )
                    self[field] = company[field]

    def copy_from_configuration( self ):
        _logger.info("Copy configuration from configuration")
