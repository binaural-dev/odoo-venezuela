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
import math

from . import versions
from .versions import *
from odoo.addons.meli_oerp.models.versions import *

from odoo.exceptions import UserError, ValidationError
from odoo.addons.meli_oerp.models.versions import *


class MercadoLibreConnectionBinding(models.Model):

    _name = "mercadolibre.binding"
    _description = "MercadoLibre Connection Binding"
    _inherit = "ocapi.connection.binding"

    #Connection reference defining mkt place credentials
    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )

class MercadoLibreConnectionBindingProductTemplate(models.Model):

    _name = "mercadolibre.product_template"
    _description = "MercadoLibre Product Binding Product Template"
    _inherit = "ocapi.connection.binding.product_template"

    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )
    company_id = fields.Many2one("res.company", related="connection_account.company_id",string="Company")
    variant_bindings = fields.One2many("mercadolibre.product","binding_product_tmpl_id",string="Product Variant Bindings")

    image_bindings = fields.One2many('mercadolibre.product.image', "binding_product_tmpl_id", string="Product Template Images")

    active = fields.Boolean(string="Product Template Active",related="product_tmpl_id.active",index=True)

    meli_title = fields.Char(string='Nombre del producto en Mercado Libre',size=256,index=True)
    meli_description = fields.Text(string='Descripción')
    meli_category = fields.Many2one("mercadolibre.category",string="Categoría de MercadoLibre")
    meli_buying_mode = fields.Selection( [("buy_it_now","Compre ahora"),("classified","Clasificado")], string='Método de compra')
    meli_price = fields.Char(string='Precio de venta', size=128,index=True)
    meli_price_fixed = fields.Boolean(string='Price is fixed')
    meli_pricelist = fields.Many2one("product.pricelist",string="Pricelist")
    meli_official_store_id = fields.Char(string="ML Off. Store Id",index=True)

    @api.onchange('meli_price_fixed')
    def _onchange_meli_price_fixed( self ):
        _logger.info("bind tpl _onchange_meli_price_fixed:"+str(self and self.name))
        for bindT in self:
            _logger.info("bind tpl  _onchange_meli_price_fixed:"+str(bindT))
            #product = self._origin
            #product = self
            for bindV in bindT.variant_bindings:
                _logger.info("bind tpl  _onchange_meli_price_fixed before::"+str(bindV.meli_price_fixed)+" new:"+str(bindT.meli_price_fixed))
                #bindV.write({'meli_price_fixed': bindT.meli_price_fixed})
                bindV.meli_price_fixed = bindT.meli_price_fixed

    @api.onchange('meli_price')
    def _onchange_meli_price( self ):
        _logger.info("bind tpl _onchange_meli_price meli_price:"+str(self and self.name))
        for bindT in self:
            _logger.info("bind tpl  _onchange_meli_price:"+str(bindT))
            #product = self._origin
            #product = self
            for bindV in bindT.variant_bindings:
                _logger.info("bind tpl  _onchange_meli_price before::"+str(bindV.meli_price)+" new:"+str(bindT.meli_price))
                #bindV.write({'meli_price': bindT.meli_price})
                bindV.meli_price = bindT.meli_price

    @api.onchange('meli_pricelist')
    def _onchange_meli_pricelist( self ):
        _logger.info("_onchange_meli_pricelist:"+str(self and self.name))
        for bindT in self:
            _logger.info("_onchange_meli_pricelist:"+str(bindT))
            #product = self._origin
            #product = self
            for bindV in bindT.variant_bindings:
                _logger.info("bind tpl  _onchange_meli_pricelist before::"+str(bindV.meli_pricelist)+" new:"+str(bindT.meli_pricelist))
                #bindV.write({'meli_pricelist': bindT.meli_pricelist})
                bindV.meli_pricelist = bindT.meli_pricelist


    meli_currency = fields.Selection([("ARS","Peso Argentino (ARS)"),
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
                                    string='Moneda')
    meli_condition = fields.Selection([ ("new", "Nuevo"),
                                        ("used", "Usado"),
                                        ("not_specified","No especificado")],
                                        'Condición del producto')
    meli_dimensions = fields.Char( string="Dimensiones del producto", size=128)
    meli_pub = fields.Boolean('Meli Publication',help='MELI Product',index=True)
    meli_master = fields.Boolean('Meli Producto Maestro',help='MELI Product Maestro',index=True)
    meli_warranty = fields.Char(string='Garantía', size=256)
    meli_listing_type = fields.Selection([("free","Libre"),("bronze","Bronce"),("silver","Plata"),("gold","Oro"),("gold_premium","Gold Premium"),("gold_special","Gold Special/Clásica"),("gold_pro","Oro Pro")], string='Tipo de lista')
    meli_attributes = fields.Text(string='Atributos')

    #meli_publications = fields.Text(compute=product_template_stats,string='Publicaciones en ML',search=search_template_stats)
    #meli_variants_status = fields.Text(compute=product_template_stats,string='Meli Variant Status')

    meli_pub_as_variant = fields.Boolean('Publicar variantes como variantes en ML',help='Publicar variantes como variantes de la misma publicación, no como publicaciones independientes.')
    meli_pub_variant_attributes = fields.Many2many(prod_att_line, relation='meli_pub_variant_attributes',column1='mercadolibre_product_template_id',column2='product_template_attribute_line_id', string='Atributos a publicar en ML',help='Seleccionar los atributos a publicar')
    meli_pub_principal_variant = fields.Many2one( 'product.product',string='Variante principal',help='Variante principal')

    meli_model = fields.Char(string="Modelo [meli]",size=256)
    meli_brand = fields.Char(string="Marca [meli]",size=256)
    meli_gender = fields.Char(string="Genero",index=True)
    meli_grid_chart_id = fields.Many2one("mercadolibre.grid.chart",string="Guia de talles")
    meli_stock = fields.Float(string="Cantidad inicial (Solo para actualizar stock)[meli]")

    meli_product_bom = fields.Char(string="Lista de materiales (skux:1,skuy:2,skuz:4) [meli]")

    meli_product_price = fields.Float(string="Precio [meli]")
    meli_product_cost = fields.Float(string="Costo del proveedor [meli]")
    meli_product_code = fields.Char(string="Codigo de proveedor [meli]")
    meli_product_supplier = fields.Char(string="Proveedor del producto [meli]")

    meli_ids = fields.Char(size=2048,string="MercadoLibre Ids.",help="ML Ids de variantes separados por coma.",index=True)
    meli_mercadolibre_banner = fields.Many2one("mercadolibre.banner",string="Plantilla Descriptiva")

    meli_catalog_listing = fields.Boolean(string='Catalog Listing')
    meli_catalog_product_id = fields.Char(string='Catalog Product Id', size=256)
    meli_catalog_item_relations = fields.Char(string='Catalog Item Relations', size=256)
    meli_catalog_automatic_relist = fields.Boolean(string='Catalog Auto Relist')

    meli_shipping_logistic_type = fields.Char(string="Logistic Type",index=True)
    meli_shipping_free = fields.Boolean(string="Shipping Free",default=False,index=True)


    meli_shipping_mode = fields.Char(string="Shipping Mode",help="Shipping modes (por usuario): custom, not_specified, me2. https://api.mercadolibre.com/users/USERID/shipping_preferences",index=True)
    meli_shipping_method = fields.Char(string="Shipping Method",help="Shipping methods: https://api.mercadolibre.com/sites/SITEID/shipping_methods",index=True)

    def meli_status_compute( self ):
        for bindT in self:
            st = None
            sst = None
            for bindv in bindT.variant_bindings:
                st = st or bindv.meli_status
                sst = sst or bindv.meli_sub_status
            bindT.meli_status = str(st)+"-"+str(sst)

    meli_status = fields.Char(string="Status ML", compute=meli_status_compute )

    def product_template_permalink(self):
        for bindT in self:
            bindT.meli_permalink = ""
            bind = bindT.variant_bindings and bindT.variant_bindings[0]
            if bind:
                bindT.meli_permalink = bind.meli_permalink

    meli_permalink = fields.Char( compute=product_template_permalink, size=256, string='Link',help='PermaLink in MercadoLibre', store=False )
    #meli_permalink_edit = fields.Char( compute=product_get_meli_update, size=256, string='Link Edit',help='PermaLink Edit in MercadoLibre', store=False )


    def update_price( self, meli_price=False, meli_pricelist=False, meli_price_fixed=False ):
        for bindT in self:

            account = bindT.connection_account
            config = account and account.configuration

            bindT.meli_pricelist = meli_pricelist or bindT.meli_pricelist
            bindT.meli_price_fixed = meli_price_fixed or bindT.meli_price_fixed
            bindT.meli_price = meli_price or (bindT.meli_price and float(bindT.meli_price)>0 and bindT.meli_price)
            # or (bind.meli_price and float(bind.meli_price)>0 and bind.meli_price)

            pl = bindT.meli_pricelist
            bind = bindT.variant_bindings and bindT.variant_bindings[0]
            pl = pl or (bind.meli_currency and bind.meli_currency in ["USD"] and config.mercadolibre_pricelist_usd and config.mercadolibre_pricelist_usd.currency_id.name=="USD" and config.mercadolibre_pricelist_usd)
            product = bind and bind.product_id
            if pl and product:
                #if manual set in pricelist
                _logger.info("Pricelist:"+str(pl and pl.name))
                if (meli_price):
                    bind.update_pl_price(meli_price=meli_price)
                return_val = get_price_from_pl( pl, product, 1.0 )
                if pl.id in return_val:
                    new_price = return_val[pl.id]

                    #added taxes here
                    tax_excluded = ml_tax_excluded(self,config=config)
                    if ( tax_excluded and product and product.taxes_id ):
                        _logger.info("Adjust taxes for publish")
                        txfixed = 0
                        txpercent = 0
                        #_logger.info("Adjust taxes")
                        for txid in product.taxes_id:
                            if (txid.type_tax_use=="sale" and not txid.price_include):
                                if (txid.amount_type=="percent"):
                                    txpercent = txpercent + txid.amount
                                if (txid.amount_type=="fixed"):
                                    txfixed = txfixed + txid.amount
                        if (txfixed>0 or txpercent>0):
                            #_logger.info("Tx Total:"+str(txtotal)+" to Price:"+str(ml_price_converted))
                            new_price = txfixed + new_price * (1.0 + txpercent*0.01)
                            #_logger.info("Price adjusted with taxes:"+str(new_price))

                    if (new_price>0):
                        bind.meli_price = new_price

            bindT.price = bindT.meli_price
            for bindv in bindT.variant_bindings:
                bindv.price = bindT.price
                bindv.meli_price = bindT.meli_price
                if (product.meli_id == bind.meli_id):
                    product.meli_price = bind.meli_price
                bindv.meli_pricelist = bindT.meli_pricelist
                bindv.meli_price_fixed = bindT.meli_price_fixed

    def product_template_post( self, context=None, meli_id=None, meli=None, account=None, product_variant=None ):
        context = context or self.env.context
        _logger.info("MercadoLibre Product template Post context: "+str(context)+" meli_id: "+str(meli_id)+" account: "+str(account))
        warningobj = self.env['meli.warning']
        custom_context = {}
        force_meli_pub = False
        force_meli_active = False
        force_meli_new_pub = False

        force_meli_new_title = False
        force_meli_new_price = False
        force_meli_new_pricelist = False

        if ("force_meli_pub" in context):
            force_meli_pub = context.get("force_meli_pub")
        if ("force_meli_active" in context):
            force_meli_active = context.get("force_meli_active")
        if ("force_meli_new_pub" in context):
            force_meli_new_pub = context.get("force_meli_new_pub")

        if ("force_meli_new_title" in context):
            force_meli_new_title = context.get("force_meli_new_title")
        if ("force_meli_new_price" in context):
            force_meli_new_price = context.get("force_meli_new_price")
        if ("force_meli_new_pricelist" in context):
            force_meli_new_pricelist = context.get("force_meli_new_pricelist")

        custom_context = {
            "force_meli_pub": force_meli_pub,
            "force_meli_active": force_meli_active,
            "force_meli_new_pub": force_meli_new_pub,

            "force_meli_new_title": force_meli_new_title,
            "force_meli_new_price": force_meli_new_price,
            "force_meli_new_pricelist": force_meli_new_pricelist
        }
        _logger.info("custom_context: "+str(custom_context))

        ret = {}
        posted_products = 0

        for bindT in self:

            account = bindT.connection_account
            company = (account and account.company_id) or self.env.user.company_id
            config = (account and account.configuration) or company
            productT = bindT.product_tmpl_id
            meli_id = bindT.conn_id
            meli_pricelist = force_meli_new_pricelist or bindT.meli_pricelist
            bindT.update_price(meli_price=force_meli_new_price,meli_pricelist=force_meli_new_pricelist)

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            if (productT.meli_pub_as_variant):
                _logger.info("Posting as variants")

                if not productT.meli_pub_variant_attributes:
                    ret = warningobj.info( title='MELI WARNING', message="Seleccione los atributos a tener en cuenta para publicar como variante en ML. (MercadoLibre Plantilla > Atributos a publicar en ML)", message_html="" )
                    return ret


                variant_principal = productT.meli_pub_principal_variant
                first_product_post = not meli_id and (not variant_principal or (variant_principal and not variant_principal.meli_id))
                new_product_post = (variant_principal and variant_principal.meli_id and not meli_id) and force_meli_new_pub
                update_product_post = (variant_principal and variant_principal.meli_id and meli_id) and not force_meli_new_pub

                if variant_principal and variant_principal.meli_id == meli_id:
                    #UPDATE POST (BASE PRODUCT)
                    _logger.info("#UPDATE POST (BASE PRODUCT)")
                    variant_principal.meli_pub = True
                    ret = variant_principal.with_context(custom_context).product_post( meli=meli, config=config )
                    if (ret and len(ret) and 'name' in ret[0]):
                        return ret[0]
                    posted_products+= 1

                    #upgrade all binded connections
                    bindT.stock = 0
                    for variant in productT.product_variant_ids:
                        if variant.meli_id:

                            #binding is anew, set with last meli_id if we can
                            meli_id = variant.meli_id
                            meli_price = variant.meli_price or productT.meli_price
                            meli_available_quantity = variant.meli_available_quantity

                            bindT.conn_id = meli_id
                            #bindT.price = meli_price
                            #meli_price = force_meli_new_price or variant.meli_price or productT.meli_price
                            #meli_pricelist = force_meli_new_pricelist or bindT.meli_pricelist
                            bindT.update_price(meli_price=force_meli_new_price,meli_pricelist=force_meli_new_pricelist)
                            bindT.stock+= float(meli_available_quantity)

                            for bind in bindT.variant_bindings:
                                bind.conn_id = meli_id
                                #bind.price = meli_price or bind.price
                                bind.update_price(meli_price=force_meli_new_price,meli_pricelist=force_meli_new_pricelist)
                    #continue;
                elif variant_principal and meli_id!=variant_principal.meli_id:
                    _logger.info("TODO: Check this bind how to post it!!! Republish as new with variants, meli_id: "+str(meli_id)+" variant_principal.meli_id: "+str(variant_principal.meli_id))
                    #binded but not principal variants.meli_id != bindT.meli_id
                    if not meli_id and productT.mercadolibre_bindings and len(productT.mercadolibre_bindings)==1 and variant_principal.meli_id:
                        #rebind
                        meli_id = variant_principal.meli_id
                        bindT.conn_id = meli_id
                        for bind in bindT.variant_bindings:
                            bind.conn_id = meli_id
                            bind.meli_id = meli_id
                    bind = bindT and bindT.variant_bindings and bindT.variant_bindings[0]
                    ret = variant_principal.with_context(custom_context).product_post( bind_tpl=bindT, bind=bind, meli=meli, config=config )
                    if (ret and len(ret) and 'name' in ret[0]):
                        return ret[0]
                    posted_products+= 1

                #No hay variante principal definida, elegimos la primera
                if not productT.meli_pub_principal_variant:
                    variant_principal = False
                    for variant in productT.product_variant_ids:
                        conditions_ok = variant._conditions_ok()
                        _logger.info("conditions_ok: "+str(conditions_ok))
                        if ( conditions_ok or variant_principal==False):

                            variant.meli_pub = True

                            if (variant_principal==False):
                                _logger.info("Posting variant principal:"+str(variant))
                                variant_principal = variant
                                productT.meli_pub_principal_variant = variant_principal
                                ret = variant_principal.with_context(custom_context).product_post( meli=meli, config=config )
                                if (ret and len(ret) and 'name' in ret[0]):
                                    return ret[0]
                                posted_products+= 1
                        else:
                            _logger.info("No condition met for:"+variant.display_name)
                _logger.info(productT.meli_pub_variant_attributes)
            else:
                for variant in productT.product_variant_ids:
                    _logger.info("product_template_post > Posting Variant: ", variant, variant.meli_pub)
                    if product_variant and product_variant.id!=variant.id:
                        #only one product variant to import on this iteration
                        continue;

                    if (force_meli_pub==True):
                        variant.meli_pub = True

                    if force_meli_new_pub:
                        meli_id = False

                    first_product_post = (not meli_id and not variant.meli_id)
                    new_product_post = (variant.meli_id and not meli_id) and force_meli_new_pub
                    update_product_post = (variant.meli_id and meli_id) and not force_meli_new_pub

                    _logger.info("meli_id:"+str(meli_id)+" variant.meli_id:"+str(variant.meli_id)+" force_meli_new_pub:"+str(force_meli_new_pub))
                    _logger.info("first_product_post:"+str(first_product_post)+" new_product_post:"+str(new_product_post)+" update_product_post:"+str(update_product_post))

                    if (variant.meli_pub and (variant.meli_id==meli_id or first_product_post) ):

                        _logger.info("Posting variant")
                        ret = variant.with_context(custom_context).product_post( meli=meli, config=config )
                        if ('name' in ret[0]):
                            return ret[0]
                        _logger.info(ret)

                        if variant.meli_id:
                            #binding is anew, set with last meli_id if we can
                            meli_id = variant.meli_id
                            meli_price = variant.meli_price
                            meli_available_quantity = variant.meli_available_quantity
                            bindT.conn_id = meli_id
                            #bindT.price = meli_price
                            bindT.update_price(meli_price=force_meli_new_price,meli_pricelist=force_meli_new_pricelist)
                            bindT.stock = meli_available_quantity
                            for bind in bindT.variant_bindings:
                                bind.conn_id = meli_id
                                #bind.price = meli_price
                                bind.update_price(meli_price=force_meli_new_price,meli_pricelist=force_meli_new_pricelist)
                                #bind.stock = meli_available_quantity

                        posted_products+= 1
                    elif (new_product_post and force_meli_new_pub):
                        _logger.info("Posting New variant Publication")
                        bind = bindT and bindT.variant_bindings and bindT.variant_bindings[0]
                        ret = variant.with_context(custom_context).product_post( bind_tpl=bindT, bind=bind, meli=meli, config=config )
                        if ('name' in ret[0]):
                            #return ret[0]
                            _logger.info(ret)
                            #self.env.cr.rollback()
                            return ret[0]
                            #_logger.info(ret)
                            #raise ValidationError(str(ret[0]))
                        if bind.meli_id:
                            #binding is anew, set with last meli_id if we can
                            meli_id = bind.meli_id
                            meli_price = bind.meli_price
                            meli_available_quantity = bind.meli_available_quantity
                            bindT.conn_id = meli_id
                            bindT.price = meli_price
                            bindT.stock = meli_available_quantity
                            for bind in bindT.variant_bindings:
                                bind.conn_id = meli_id
                                bind.meli_id = meli_id
                                bind.price = meli_price
                                #bind.stock = meli_available_quantity
                        _logger.info(ret)
                        posted_products+= 1
                    elif (meli_id and variant.meli_id):
                        bind = bindT and bindT.variant_bindings and bindT.variant_bindings[0]
                        ret = variant.with_context(custom_context).product_post( bind_tpl=bindT, bind=bind, meli=meli, config=config )
                        if ('name' in ret[0]):
                            #return ret[0]
                            _logger.info(ret)
                            #raise ValidationError(str(ret[0]))
                            #self.env.cr.rollback()
                            return ret[0]

                        if bind.meli_id:
                            #binding is anew, set with last meli_id if we can
                            meli_id = bind.meli_id
                            meli_price = bind.meli_price
                            meli_available_quantity = bind.meli_available_quantity
                            bindT.conn_id = meli_id
                            bindT.price = meli_price
                            bindT.stock = meli_available_quantity
                            for bind in bindT.variant_bindings:
                                bind.conn_id = meli_id
                                bind.meli_id = meli_id
                                bind.price = meli_price
                        _logger.info(ret)
                        posted_products+= 1
                    else:
                        #if error_product_post:
                        #    _logger.info("error_product_post: "+str(error_product_post))
                        #binding is new, take the first variant meli_id:
                        error = "No meli_pub or meli_id for:"+variant.display_name + " bind>meli_id: "+str(meli_id) + " meli_pub:" + str(variant.meli_pub) + " variant.meli_id:"+str(variant.meli_id)
                        #+ " error_product_post:"+str(error_product_post)
                        raise ValidationError(error)
                        _logger.info(error)

        if (posted_products==0):
            raise ValidationError("Se intentaron publicar 0 productos. Debe forzar las publicaciones o marcar el producto con el campo Meli Publication, debajo del titulo. Puede tambien intentar revincular el producto.")
            ret = warningobj.info( title='MELI WARNING', message="Se intentaron publicar 0 productos. Debe forzar las publicaciones o marcar el producto con el campo Meli Publication, debajo del titulo. Puede tambien intentar revincular el producto.", message_html="" )

        return ret

    def product_template_post_stock( self, context=None, meli_id=None, meli=None, account=None ):
        _logger.info("product_template_post_stock >> MercadoLibre Product Template Post Stock")
        ret = {}
        for bindT in self:

            account = bindT.connection_account
            product = bindT.product_tmpl_id
            meli_id = bindT.conn_id
            stock = 0
            stock_update = ""
            stock_error = ""

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            for bindv in bindT.variant_bindings:
                bindv.product_post_stock(meli=meli)
                stock+= (bindv.stock or bindv.meli_available_quantity)
                stock_error+= str(bindv.stock_error)
                stock_update = bindv.stock_update

            bindT.stock = stock
            bindT.stock_error = stock_error
            bindT.stock_update = stock_update

        return ret

    def product_template_post_price( self, context=None, meli_id=None, meli=None, account=None ):
        _logger.info("product_template_post_price >> MercadoLibre Product Template Post Prices")
        ret = {}
        for bindT in self:

            account = bindT.connection_account
            product = bindT.product_tmpl_id
            meli_id = bindT.conn_id

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            bindT.update_price()

            for bindv in bindT.variant_bindings:
                bindv.product_post_price(meli=meli)

        return ret

    def product_template_update( self, meli=None ):
        _logger.info("template product_template_update >> MercadoLibre Product template Update "+str(meli))
        ret = {}
        for bindT in self:

            account = bindT.connection_account
            product = bindT.product_tmpl_id
            meli_id = bindT.conn_id

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            rjson = account.fetch_meli_product( meli_id = meli_id, meli = meli )

            if ( product and product.meli_pub_as_variant and product.meli_pub_principal_variant.id ):
                _logger.info("template product_template_update >> Updating principal variant")
                #como puede que no exista aun el binding de variant??? que hacemos??
                #chequear si tiene un binding de variante:  y ejecutar ese binding
                pvbind = self.env["mercadolibre.product"].search([  ('conn_id','=',meli_id),
                                                                    ('product_tmpl_id','=',product.id),
                                                                    ('product_id','=',product.meli_pub_principal_variant.id),
                                                                    ('connection_account','=',account.id)],limit=1)
                if pvbind:
                    _logger.info("Founded principal binding variant: getting product: "+str(pvbind.name)+" meli: "+str(meli))
                    pvbind.product_meli_get_product( meli=meli )
                else:
                    ret = product.meli_pub_principal_variant.product_meli_get_product( account=account, meli=meli, rjson=rjson )
                    _logger.info("ret:"+str(ret))
                    _logger.info("MercadoLibre Product template Update >> Updating principal variant >> copy_from_rjson (recursive)")
                    bindT.copy_from_rjson( rjson=rjson, meli=meli )
            else:
                for variant in product.product_variant_ids:
                    #_logger.info("Variant:", variant)
                    if (variant.meli_pub):
                        _logger.info("template product_template_update >> calling product_meli_get_product Updating variant")
                        pvbind = self.env["mercadolibre.product"].search([  ('conn_id','=',meli_id),
                                                                            ('product_tmpl_id','=',product.id),
                                                                            ('product_id','=',variant.id),
                                                                            ('connection_account','=',account.id)],limit=1)
                        ret = {}
                        if pvbind:
                            pvbind.product_meli_get_product( meli=meli, rjson=rjson )
                        else:
                            ret = variant.product_meli_get_product(account=account, meli=meli, rjson=rjson)
                        if ('name' in ret):
                            return ret

        return ret

        #if (product_template):
        #    bindT = product_template.mercadolibre_bind_to( account=account, meli_id=meli_id, bind_variants=True )
        #    if bindT:
                # from_meli_oerp = True copy form recent imported
        #        bindT.fetch_meli_product( meli=meli, from_meli_oerp=True, fetch_variants=True )

    def category_predictor( self ):
        _logger.info("MercadoLibre Product template Category Predictor")

    def copy_from_meli_oerp( self ):
        for bindT in self:
            productT = bindT.product_tmpl_id
            #basic info
            bindT.meli_title = productT.meli_title
            bindT.meli_description = productT.meli_description
            bindT.meli_category = productT.meli_category
            bindT.meli_price = productT.meli_price
            bindT.price = productT.meli_price
            bindT.meli_stock = productT.meli_stock
            bindT.stock = productT.meli_stock

            #attributes
            bindT.meli_attributes = productT.meli_attributes
            bindT.meli_model = productT.meli_model
            bindT.meli_brand = productT.meli_brand
            bindT.meli_gender = productT.meli_gender
            bindT.meli_grid_chart_id = productT.meli_grid_chart_id


            #publish ref info
            bindT.meli_pub = productT.meli_pub
            bindT.meli_master = productT.meli_master
            bindT.meli_ids = productT.meli_ids

            #config info
            bindT.meli_currency = productT.meli_currency
            bindT.meli_condition = productT.meli_condition
            bindT.meli_warranty = productT.meli_warranty
            bindT.meli_listing_type = productT.meli_listing_type
            bindT.meli_dimensions = productT.meli_dimensions
            bindT.sku = productT.product_variant_ids.mapped("default_code") or productT.default_code
            bindT.barcode = productT.product_variant_ids.mapped("barcode") or productT.barcode

            bindT.meli_shipping_logistic_type = str(productT.product_variant_ids.mapped("meli_shipping_logistic_type"))
            bindT.meli_shipping_free =  productT.product_variant_ids and productT.product_variant_ids[0].meli_shipping_free


    def copy_from_rjson( self, rjson, meli=None ):
        _logger.info("template bind >> copy_from_rjson")
        if not rjson:
            return
        for bindT in self:
            account = bindT.connection_account
            config = account.configuration
            product_tmpl_id = bindT.product_tmpl_id
            #basic info
            catid, wwwid = self.env["mercadolibre.category"].meli_get_category( rjson['category_id'], meli=meli, create_missing_website=config.mercadolibre_create_website_categories )
            desplain = ("description" in rjson and rjson["description"]) or None
            meli_ids = rjson["id"]
            #seller_sku = product_tmpl_id.product_variant_ids.mapped("default_code") or
            #            ("seller_sku" in rjson and rjson["seller_sku"]) or
            #            product_tmpl_id.default_code
            #barcode = product_tmpl_id.product_variant_ids.mapped("barcode") or
            #        ("barcode" in rjson and rjson["barcode"]) or
            #        product_tmpl_id.barcode
            seller_sku = (rjson and "seller_skus" in rjson and rjson["seller_skus"])
            seller_sku = seller_sku or (rjson and "seller_sku" in rjson and rjson["seller_sku"])

            barcode = (rjson and "barcodes" in rjson and rjson["barcodes"])
            barcode = barcode or (rjson and "barcode" in rjson and rjson["barcode"])

            fields = {
                #'meli_permalink': rjson['permalink'],
                'meli_title': rjson['title'].encode("utf-8"),
                'meli_listing_type': rjson['listing_type_id'],
                'meli_buying_mode':rjson['buying_mode'],
                'meli_price': str(rjson['price']),
                'price': str(rjson['price']),
                'meli_currency': rjson['currency_id'],
                'meli_condition': rjson['condition'],
                #'meli_available_quantity': rjson['available_quantity'],
                'meli_warranty': rjson['warranty'],
                'meli_category': catid,
                'meli_ids': meli_ids,
                'sku': seller_sku or "",
                'barcode': barcode or "",
                'stock': rjson['available_quantity']
                #'meli_imagen_link': rjson['thumbnail'],
                #'meli_video': str(vid),
                #'meli_dimensions': meli_dim_str,
            }
            if desplain:

                #publication specific banner
                mlbanner = product_tmpl_id.meli_mercadolibre_banner
                #configuration banner
                mlbanner = mlbanner or (config and config.mercadolibre_banner)
                meli_description = ""
                if (mlbanner):
                    #get the text, not the header nor the footer
                    meli_description = mlbanner.get_from_ml_description( desplain )

                fields["meli_description"] = meli_description


            if "meli_official_store_id" in bindT._fields:
                fields["meli_official_store_id"] = ('official_store_id' in rjson and rjson['official_store_id']) or ""
                meli_official_store_id = fields["meli_official_store_id"]
                if (str(account.official_store_id)!=str(meli_official_store_id)):
                    #change account
                    #_logger.info("copy_from_rjson > changing account:"+str(meli_official_store_id))
                    account_store_id = self.env['mercadolibre.account'].search( [( 'official_store_id', '=ilike', str(meli_official_store_id) )], limit=1 )
                    #_logger.info("copy_from_rjson > account_store_id:"+str(account_store_id))
                    if (account_store_id):
                        bindT.connection_account = account_store_id
                        account = bindT.connection_account
                        config = account.configuration




            meli_shipping_logistic_type = ( rjson and "shipping" in rjson and "logistic_type" in rjson["shipping"] and rjson["shipping"]["logistic_type"] ) or ""
            meli_shipping_logistic_type and fields.update({'meli_shipping_logistic_type': meli_shipping_logistic_type })

            meli_shipping_free = ( rjson and "shipping" in rjson and "free_shipping" in rjson["shipping"] and rjson["shipping"]["free_shipping"] ) or False
            meli_shipping_free and fields.update({'meli_shipping_free': meli_shipping_free })

            #_logger.info("copy in bindT: "+str(fields))
            bindT.write(fields)

            for bind in bindT.variant_bindings:
                bind.connection_account = account
                bind.copy_from_rjson( rjson=rjson, meli=meli )

            #seller_sku = product_tmpl_id.product_variant_ids.mapped("default_code") or ("seller_sku" in rjson and rjson["seller_sku"]) or product_tmpl_id.default_code
            #barcode = product_tmpl_id.product_variant_ids.mapped("barcode") or ("barcode" in rjson and rjson["barcode"]) or product_tmpl_id.barcode
            #fields = {'sku': seller_sku or "",'barcode': barcode or ""}
            #bindT.write(fields)


    def fetch_meli_product( self, meli = None, rjson = None, from_meli_oerp = False, fetch_variants = False ):
        _logger.info("binding template fetch_meli_product")

        #fetch product full data from MELI into binding
        for bindT in self:

            account = bindT.connection_account
            meli_id = bindT.conn_id
            productT = bindT.product_tmpl_id

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            if not meli_id or not meli:
                continue;

            if from_meli_oerp: #TODO, check validity and meli_id in bindT.product_tmpl_id.meli_ids:
                bindT.copy_from_meli_oerp()
            else:
                rjson = rjson or account.fetch_meli_product( meli_id=meli_id, meli=meli )
                bindT.copy_from_rjson( rjson=rjson, meli=meli )

            if fetch_variants:
                pv_bindings = self.env["mercadolibre.product"].search([("conn_id","=",meli_id),
                                                                        ("binding_product_tmpl_id","=",bindT.id),
                                                                        ("connection_account","=",account.id)])
                if pv_bindings:
                    _logger.info("Binding template fetch_meli_product >> Fetching variants pv_bindings: "+str(len(pv_bindings)))
                    for pv_bind in pv_bindings:
                        try:
                            pv_bind.fetch_meli_product( meli = meli, rjson = rjson, from_meli_oerp = from_meli_oerp )
                        except Exception as e:
                            _logger.error("Error fetching variant product binding: "+str(pv_bind)+str(e))
                else:
                    _logger.error("Missing variant bindings to fetch meli data")


    def product_meli_status_put( self, context=None, status=None, meli=False):

        company = self.env.user.company_id
        account = self.connection_account
        config = (account and account.configuration) or company
        company = ("company_id" in config._fields and config.company_id) or company

        meli_id = self.conn_id
        if not meli:
            meli = self.env['meli.util'].get_new_instance(company, account)

            if meli.need_login():
                return meli.redirect_login()

        if meli_id and status and (status in ['paused','closed','active']):
            response = meli.put("/items/"+str(meli_id), { 'status': status }, {'access_token':meli.access_token})
            if response:
                _logger.info(response.json())
        else:
            _logger.error("Undefined status set, meli_id: "+str(meli_id)+" status: "+str(status))
        return {}

    def product_meli_block(self):
        self.meli_update_stock_blocked = True
        #product = bind.product_tmpl_id
        #product.meli_update_stock_blocked = True
        #for variant in product.product_variant_ids:
        #    product.meli_update_stock_blocked = True

    def product_meli_unblock(self):
        self.meli_update_stock_blocked = False
        #product = bind.product_tmpl_id
        #product.meli_update_stock_blocked = False
        #for variant in product.product_variant_ids:
            #product.meli_update_stock_blocked = False


    def product_meli_status_close( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product Tpl product_meli_status_close")
        return self.product_meli_status_put(context=context,status='closed',meli=meli)

    def product_meli_status_pause( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product Tpl product_meli_status_pause")
        self.product_meli_block()
        return self.product_meli_status_put(context=context,status='paused',meli=meli)

    def product_meli_status_active( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product Tpl product_meli_status_active")
        self.product_meli_unblock()
        return self.product_meli_status_put(context=context,status='active',meli=meli)

    def product_meli_delete( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product Tpl product_meli_delete")
        company = self.env.user.company_id
        account = self.connection_account
        config = (account and account.configuration) or company
        company = ("company_id" in config._fields and config.company_id) or company

        meli_id = self.conn_id

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company, account)
        if meli.need_login():
            return meli.redirect_login()

        if meli_id:
            response = meli.put("/items/"+str(meli_id), { 'deleted': 'true' }, {'access_token':meli.access_token})

            rjson = response.json()
            _logger.info( rjson )
            ML_status = rjson["status"]
            if "error" in rjson:
                ML_status = rjson["error"]
            if "sub_status" in rjson:
                if len(rjson["sub_status"]) and rjson["sub_status"][0]=='deleted':
                    #product.write({ 'meli_id': '','meli_id_variation': '' })
                    _logger.info("Deleted ok: TODO: Delete template binding, and meli_id on base product...")

        return {}

    def product_template_stats(self):
        _logger.info("bind template >> product_template_stats")
        for bind in self:

            _pubs = ""
            _stats = ""

            product = bind.product_tmpl_id

            if product and 1==2:
                for variant in product.product_variant_ids:
                    if (variant.meli_pub):
                        if ( (variant.meli_status=="active" or variant.meli_status=="paused") and variant.meli_id):
                            ml_full_status = variant.meli_status
                            if (variant.meli_sub_status):
                                ml_full_status+= ' ('+str(variant.meli_sub_status)+')'
                            if (len(_pubs)):
                                _pubs = _pubs + "|" + variant.meli_id + ":" + ml_full_status
                            else:
                                _pubs = variant.meli_id + ":" + ml_full_status

                            if (variant.meli_status=="active"):
                                _stats = "active"

                            if (_stats == "" and variant.meli_status=="paused"):
                                _stats = "paused"

            #bind.meli_publications = _pubs
            bind.meli_variants_status = _stats

        return {}

    def product_template_unbind( self ):

        for bindT in self:
            product_template = bindT.product_tmpl_id
            if product_template:
                res = product_template.mercadolibre_unbind_from( account=bindT.connection_account, meli_id=bindT.conn_id )
                if res and 'name' in res:
                    return res

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def product_template_rebind( self ):

        for bindT in self:
            product_template = bindT.product_tmpl_id
            if product_template:
                res = product_template.mercadolibre_bind_to( account=bindT.connection_account, meli_id=bindT.conn_id )
                if res and 'name' in res:
                    return res
        return True


    def _variations( self, config = None ):
        self.ensure_one()
        for bindT in self:
            return bindT.product_tmpl_id._variations( config = config )

    meli_variants_status = fields.Text(compute=product_template_stats,string='Meli Variant Status')

    def query_questions( self, meli=None, config=None ):

        _logger.info("mercadolibre.product_template >> query_questions: meli:"+str(meli)+" config:"+str(config) )

        for bindT in self:

            account = bindT.connection_account
            config = config or account.configuration
            productT = bindT.product_tmpl_id
            meli_id = bindT.conn_id

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            response = meli.get("/questions/search?item_id="+str(meli_id), {'access_token':meli.access_token})
            questions_json = response.json()
            questions_obj = self.env['mercadolibre.questions']

            if 'questions' in questions_json:
                questions = questions_json['questions']
                #_logger.info( questions )
                cn = 0
                for Question in questions:
                    cn = cn + 1

                    question = self.env["mercadolibre.questions"].process_question( Question=Question, meli=meli, config=config )

    meli_questions = fields.One2many( "mercadolibre.questions", "product_template_binding", string="Preguntas" )
    meli_update_stock_blocked = fields.Boolean(string="Bloquea publicacion",default=False,index=True)

    @api.onchange('name')
    def _change_meli_title(self):
        for b in self:
            b.meli_title = b.name
            for bb in b.variant_bindings:
                bb.name = b.name
                bb.meli_title = b.meli_title

    @api.depends('name')
    def change_meli_title(self):
        for b in self:
            b.meli_title = b.name
            for bb in b.variant_bindings:
                bb.name = b.name
                bb.meli_title = b.meli_title


class MercadoLibreConnectionBindingProductVariant(models.Model):

    _name = "mercadolibre.product"
    _description = "MercadoLibre Product Binding Product"
    #_inherit = ["mercadolibre.product_template","ocapi.connection.binding.product"]
    _inherit = ["ocapi.connection.binding.product"]

    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )
    company_id = fields.Many2one("res.company", related="connection_account.company_id",string="Company")
    binding_product_tmpl_id = fields.Many2one("mercadolibre.product_template",string="Product Template Binding")

    image_bindings = fields.One2many('mercadolibre.product.image', "binding_product_variant_id", string="Product Variant Images")

    def product_get_meli_update( self ):

        _logger.info("bind variant >> product_get_meli_update")

        warningobj = self.env['meli.warning']
        product_obj = self.env['product.product']

        ML_status = "unknown"
        ML_sub_status = ""
        ML_permalink = ""
        ML_permalink_edit = ""
        ML_state = False
        #meli = None

        for product in self:

            account = product.connection_account
            company = (account and account.company_id) or self.env.user.company_id
            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                ML_status = "unknown"
                ML_permalink = ""
                ML_permalink_edit = ""
                ML_state = True

            if product.conn_id and not product.meli_id:
                product.meli_id = product.conn_id

            if product.meli_id and not meli.need_login():
                response = meli.get( "/items/"+product.meli_id, { 'access_token': meli.access_token } )
                rjson = response.json()
                if rjson and "error" in rjson:
                    _logger.error(str(rjson))
                elif rjson:
                    if "status" in rjson:
                        ML_status = rjson["status"]
                    if "permalink" in rjson:
                        ML_permalink = rjson["permalink"]
                        ML_permalink_edit = company.get_ML_LINK_URL(meli=meli)+str("publicaciones/")+str(product.meli_id)+str("/modificar")
                    if "error" in rjson:
                        ML_status = rjson["error"]
                        ML_permalink = ""
                    if "sub_status" in rjson:
                        if len(rjson["sub_status"]):
                            ML_sub_status =  rjson["sub_status"][0]
                            if ( ML_sub_status =='deleted' ):
                                product.write({ 'meli_id': '','meli_id_variation': '' })

            product.meli_status = ML_status
            product.meli_sub_status = ML_sub_status
            product.meli_permalink = ML_permalink
            product.meli_permalink_edit = ML_permalink_edit
            product.meli_state = ML_state

#    meli_pub_variant_attributes = fields.Many2many(prod_att_line, relation='meli_pub_variant_attributes',column1='ml_template_id',column2='att_line_id', string='Atributos a publicar en ML',help='Seleccionar los atributos a publicar')

    #typical values
    meli_title = fields.Char(string='Nombre del producto en Mercado Libre',size=256,index=True)
    meli_description = fields.Text(string='Descripción')
    meli_category = fields.Many2one("mercadolibre.category","Categoría de MercadoLibre")
    meli_price = fields.Char( string='Precio',help='Precio de venta en ML', size=128,index=True)
    meli_price_fixed = fields.Boolean(string='Price is fixed')
    meli_pricelist = fields.Many2one("product.pricelist",string="Pricelist")
    active = fields.Boolean(string="Product Active",related="product_id.active",index=True)

    @api.onchange('meli_price_fixed')
    def _onchange_meli_price_fixed( self ):
        _logger.info("_onchange_meli_price_fixed:"+str(self and self.name))
        for bindV in self:
            _logger.info("_onchange_meli_price_fixed:"+str(bindV))
            #product = self._origin
            #product = self
            bindT = bindV.binding_product_tmpl_id
            if bindT:
                bindT.write({'meli_price_fixed': bindV.meli_price_fixed})
                for bindV2 in bindT.variant_bindings:
                    _logger.info("_onchange_meli_price_fixed bind variant before::"+str(bindV2.meli_price_fixed))
                    #bindV2.write({'meli_price_fixed': bindT.meli_price_fixed})
                    bindV2.meli_price_fixed = bindT.meli_price_fixed

    @api.onchange('meli_price')
    def _onchange_meli_price( self ):
        _logger.info("_onchange_meli_price:"+str(self and self.name))
        for bindV in self:
            _logger.info("_onchange_meli_price:"+str(bindV))
            #product = self._origin
            #product = self
            bindT = bindV.binding_product_tmpl_id
            if bindT:
                bindT.write({'meli_price': bindV.meli_price})
                bindT.price = bindT.meli_price
                for bindV2 in bindT.variant_bindings:
                    _logger.info("_onchange_meli_price bind variant before::"+str(bindV2.meli_price))
                    #bindV2.write({'meli_price': bindT.meli_price})
                    bindV2.meli_price = bindT.meli_price
                    bindV2.price = bindV2.meli_price

    @api.onchange('meli_pricelist')
    def _onchange_meli_pricelist( self ):
        _logger.info("_onchange_meli_pricelist:"+str(self and self.name))
        for bindV in self:
            _logger.info("_onchange_meli_pricelist:"+str(bindV))
            #product = self._origin
            #product = self
            bindT = bindV.binding_product_tmpl_id
            if bindT:
                bindT.write({'meli_pricelist': bindV.meli_pricelist})
                for bindV2 in bindT.variant_bindings:
                    _logger.info("_onchange_meli_pricelist bind variant before::"+str(bindV2.meli_pricelist))
                    #bindV2.write({'meli_pricelist': bindT.meli_pricelist})
                    bindV2.meli_pricelist = bindT.meli_pricelist

    meli_dimensions = fields.Char( string="Dimensiones del producto", size=128)
    meli_pub = fields.Boolean('Meli Publication',help='MELI Product',index=True)

    meli_buying_mode = fields.Selection( [("buy_it_now","Compre ahora"),("classified","Clasificado")], string='Método de compra')
    meli_currency = fields.Selection([("ARS","Peso Argentino (ARS)"),
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
                                        string='Moneda')
    meli_condition = fields.Selection([ ("new", "Nuevo"), ("used", "Usado"), ("not_specified","No especificado")],'Condición del producto')
    meli_warranty = fields.Char(string='Garantía', size=256)
    meli_listing_type = fields.Selection([("free","Libre"),("bronze","Bronce"),("silver","Plata"),("gold","Oro"),("gold_premium","Gold Premium"),("gold_special","Gold Special/Clásica"),("gold_pro","Oro Pro")], string='Tipo de lista')

    #post only fields
    meli_post_required = fields.Boolean(string='Publicable', help='Este producto es publicable en Mercado Libre')

    #TODO deprecated
    meli_id = fields.Char(string='ML Id', help='Id del item asignado por Meli', size=256, index=True)
    #meli_description_banner_id = fields.Many2one("mercadolibre.banner",string="Description Banner")
    meli_mercadolibre_banner = fields.Many2one("mercadolibre.banner",string="Plantilla Descriptiva")

    meli_buying_mode = fields.Selection(string='Método',help='Método de compra',selection=[("buy_it_now","Compre ahora"),("classified","Clasificado")])
    meli_available_quantity = fields.Integer(string='Cantidades', help='Cantidad disponible a publicar en ML')
    meli_imagen_logo = fields.Char(string='Imagen Logo', size=256)
    meli_imagen_id = fields.Char(string='Imagen Id', size=256)
    meli_imagen_link = fields.Char(string='Imagen Link', size=256)
    meli_imagen_hash = fields.Char(string='Imagen Hash')
    meli_multi_imagen_id = fields.Char(string='Multi Imagen Ids', size=512)
    meli_video = fields.Char( string='Video (id de youtube)', size=256)

    def _meli_stock_moves_update( self ):
        for bind in self:
            bind.meli_stock_moves_update = bind.product_id and bind.product_id.meli_stock_moves_update
            bind._meli_stock_status()

    def process_meli_stock_moves_update( self ):
        for bind in self:
            bind._meli_stock_moves_update()


    meli_stock_moves_update = fields.Datetime(compute=_meli_stock_moves_update,string="Stock Last Move",help="Ultimo movimiento de stock")

    #meli_stock_moves_ids = fields.One2many(related="product.stock_move_ids")

    def _meli_stock_status( self ):
        for bind in self:

            bind.meli_stock_status = 'revision'

            if ( bind.stock_error != 'Ok' ):

                bind.meli_stock_status = 'revision_error'

                if ( bind.stock_error and 'fulfillment' in bind.stock_error ):

                    bind.meli_stock_status = 'revision_fulfillment'

                if ( bind.stock_error and "has_bids" in bind.stock_error ):

                    bind.meli_stock_status = 'revision_has_bids'

            else:
                if (bind.meli_stock_moves_update):
                    if (bind.stock_update):
                        if ( bind.meli_stock_moves_update > bind.stock_update ):
                            bind.meli_stock_status = 'update'
                        else:
                            bind.meli_stock_status = 'updated'
                    else:
                        bind.meli_stock_status = 'update'
                else:
                    bind.meli_stock_status = 'revision_unmoved'

    meli_stock_status = fields.Selection(selection=[('update','Actualizar'),('updated','Actualizado'),('revision','Revisar'),('revision_unmoved','Revisar sin movimientos'),('revision_error','Revisar con error'),('revision_fulfillment','Fulfillment'),('revision_has_bids','No se puede actualizar por ventas activas')],string="Status de stock",compute=_meli_stock_status,store=True,index=True)

    def get_stock_str(self,meli=None):
        stocks = []
        stocks_str = ""
        stocks_on_hand = 0.0
        stocks_available = 0.0
        stocks_meli = 0.0
        #ss = variant._product_available()
        bindv = self
        variant = bindv.product_id
        account = bindv.connection_account
        if not variant or not account:
            return stocks_str, stocks_on_hand, stocks_available, stocks_meli

        config = account.configuration
        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )
        #_logger.info("account.configuration.publish_stock_locations")
        #_logger.info(account.configuration.publish_stock_locations.mapped("id"))
        #locids = account.configuration.publish_stock_locations.mapped("id")
        meli_id = bindv.conn_id
        meli_id_variation = bindv.conn_variation_id

        locids = variant._meli_get_location_id( meli_id=meli_id, meli=meli,config=config)
        #_logger.info("locids:"+str(locids))
        sq = None
        if (locids):
            locids_id = [locid.id for locid in locids]
            #_logger.info("locids_id:"+str(locids_id))
            sq = self.env["stock.quant"].search([('product_id','=',variant.id),('location_id','in',locids_id)],order="location_id asc")
        if (sq):
            #_logger.info( sq )
            #_logger.info( sq.name )
            for s in sq:
                #TODO: filtrar por configuration.locations
                #TODO: merge de stocks
                #TODO: solo publicar available
                if ( s.location_id.usage == "internal"):
                    #_logger.info( s )
                    sjson = {
                        "warehouseId": s.location_id.id,
                        "warehouse": s.location_id.display_name,
                        "quantity": s.quantity,
                        "reserved": s.reserved_quantity,
                        "available": s.quantity - s.reserved_quantity
                    }
                    #stocks.append(sjson)
                    stocks_str+= str(sjson["warehouse"])+str(": ")+str(sjson["quantity"])+str("/")+str(str(sjson["available"]))
                    stocks_str+= " "
                    stocks_on_hand+= sjson["quantity"]
                    stocks_available+= sjson["available"]
                    #variant.stock = sjson["available"]
            res = "/items/%s" % (meli_id)
            #_logger.info("res:"+str(res)+" meli.access_token:"+str(meli.access_token))
            response = meli.get( res, {'access_token':meli.access_token})
            rjson = response.json()

            if (meli_id_variation):
                if rjson and "variations" in rjson:
                    for var in rjson["variations"]:
                        #_logger.info("var:"+str(var))
                        if (str(var["id"])==str(meli_id_variation)):
                            #_logger.info("var YES:"+str(var))
                            stocks_meli = var["available_quantity"]
                            break;

            else:
                if rjson and "available_quantity" in rjson and rjson["available_quantity"]:
                    stocks_meli = rjson["available_quantity"]

        return stocks_str, stocks_on_hand, stocks_available, stocks_meli

    def _search_stock_resume_on_hand(self, operator, value):
        ids = []
        if (operator == '>' or operator == '<' or operator == '=' or operator == '>=' or operator == '<='):

            company = self.env.user.company_id
            account = company.producteca_connections and company.producteca_connections[0]
            if not account:
                return []

            locids = account.configuration.publish_stock_locations.mapped("id")
            sq = self.env["stock.quant"].search([('location_id','in',locids),('quantity',operator,value)],order="quantity asc")
            if sq:
                pids = sq.mapped("product_id")
                vbids = self.search([('product_id','in', pids.ids)])
                if vbids:
                    ids = [('id','in',vbids.ids)]

        return ids

    def _search_stock_resume_available(self, operator, value):
        ids = []
        if (operator == '>' or operator == '<' or operator == '=' or operator == '>=' or operator == '<='):

            company = self.env.user.company_id
            account = company.producteca_connections and company.producteca_connections[0]

            if not account:
                return []
            locids = account.configuration.publish_stock_locations.mapped("id")

            rsq = self.env["stock.quant"].search([('location_id','in',locids),('reserved_quantity','>',0.0)],order="reserved_quantity asc")
            sq = self.env["stock.quant"].search([('location_id','in',locids),('quantity',operator,value)],order="quantity asc")

            pids = []

            if sq:
                products_quantity = sq.mapped("product_id")
                pids = products_quantity

            if rsq:
                products_reserved = rsq.mapped("product_id")
                pids_reserved = products_reserved.ids
                products_not_reserved = products_quantity - products_reserved
                for q in rsq:
                    qav = q.quantity - q.reserved_quantity
                    if OPERATORS[operator](qav, value):
                        products_not_reserved+= q.product_id
                pids = products_not_reserved

            if pids:
                #_logger.info(pids.ids)
                vbids = self.search([('product_id','in', pids.ids)])
                #_logger.info(vbids)
                if vbids:
                    ids = [('id','in',vbids.ids)]

        return ids


    def _meli_stock_resume(self):
        #_logger.info("Calculate stock resume")
        account_def = None
        meli = None
        for bind in self:
            account = bind.connection_account
            if (account_def!=account):
                account_def = account
                meli = None
                if not meli:
                    meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            bind.meli_stock_resume = ""
            stocks_str, stocks_on_hand, stocks_available, stocks_meli = bind.get_stock_str(meli=meli)
            bind.meli_stock_resume = stocks_str
            bind.meli_stock_resume_on_hand = stocks_on_hand
            bind.meli_stock_resume_available = stocks_available
            bind.meli_stock_resume_mercadolibre = stocks_meli

    meli_stock_resume = fields.Char(string="Stock Resumen", compute="_meli_stock_resume", store=False )
    meli_stock_resume_on_hand = fields.Float(string="En mano")
    meli_stock_resume_available = fields.Float(string="Disponible")
    meli_stock_resume_mercadolibre = fields.Float(string="Stock en MercadoLibre")
    #meli_stock_resume_on_hand = fields.Float(string="Qty On hand", compute="_meli_stock_resume"
                        #, search="_search_stock_resume_on_hand"
    #                    )
    #meli_stock_resume_available = fields.Float(string="Qty Available", compute="_meli_stock_resume"
    #                    #, search="_search_stock_resume_available"
    #                    )
    meli_permalink = fields.Char( compute=product_get_meli_update, size=256, string='Link',help='PermaLink in MercadoLibre', store=False )
    meli_permalink_edit = fields.Char( compute=product_get_meli_update, size=256, string='Link Edit',help='PermaLink Edit in MercadoLibre', store=False )
    meli_state = fields.Boolean( compute=product_get_meli_update, string='Login',help="Inicio de sesión requerida", store=False )
    meli_status = fields.Char( compute=product_get_meli_update, size=128, string='Status', help="Estado del producto en ML", store=False )
    meli_sub_status = fields.Char( compute=product_get_meli_update, size=128, string='Sub status',help="Sub Estado del producto en ML", store=False )

    meli_last_status = fields.Char( string="Last Status",index=True )

    meli_attributes = fields.Text(string='Atributos')

    meli_model = fields.Char(string="Modelo",size=256)
    meli_brand = fields.Char(string="Marca",size=256)
    meli_gender = fields.Char(string="Genero",index=True)
    meli_grid_chart_id = fields.Many2one("mercadolibre.grid.chart",string="Guia de talles")

    meli_default_stock_product = fields.Many2one("product.product","Producto de referencia para stock")

    #TODO deprecated
    meli_id_variation = fields.Char( string='Variation Id',help='Id de Variante de Meli', size=256)

    meli_catalog_listing = fields.Boolean(string='Catalog Listing')
    meli_catalog_product_id = fields.Char(string='Catalog Product Id', size=256)
    meli_catalog_item_relations = fields.Char(string='Catalog Item Relations', size=256)
    meli_catalog_automatic_relist = fields.Boolean(string='Catalog Auto Relist')

    meli_shipping_logistic_type = fields.Char(string="Logistic Type",index=True)
    meli_shipping_free = fields.Boolean(string="Shipping Free",default=False,index=True)


    meli_inventory_id = fields.Char(string="Inventory Id",index=True)

    meli_shipping_mode = fields.Char(string="Shipping Mode",help="Shipping modes (por usuario): custom, not_specified, me2. https://api.mercadolibre.com/users/USERID/shipping_preferences",index=True)
    meli_shipping_method = fields.Char(string="Shipping Method",help="Shipping methods: https://api.mercadolibre.com/sites/SITEID/shipping_methods",index=True)

    meli_max_purchase_quantity = fields.Integer(string='Max Compra', help='Cantidad maxima por compra en ML')
    meli_manufacturing_time = fields.Char(string='Manufacturing time', help='Tiempo de fabricacion (30 días)')

    #meli_update_stock_blocked = fields.Boolean(string="Bloquea publicacion",default=False,index=True)

    def copy_from_meli_oerp( self ):
        for bind in self:
            product = bind.product_id
            _logger.info("variant bind copy_from_meli_oerp meli_id: %s meli_id_variation: %s" % (str(bind.conn_id),str(bind.conn_variation_id)))
            _logger.info("variant bind copy_from_meli_oerp p.meli_id: %s p.meli_id_variation: %s" % (str(product.meli_id),str(product.meli_id_variation)))
            if (product.meli_id_variation!=bind.conn_variation_id):
                pb2 = self.env["mercadolibre.product"].search([ ('conn_id','=',product.meli_id),
                                                          ('conn_variation_id','=',product.meli_id_variation),
                                                          ('product_tmpl_id','=',bind.product_tmpl_id),
                                                          ('connection_account','=',bind.connection_account.id)])
                if pb2:
                    _logger.info("Look! Duplicates for: "+str(product.meli_id_variation))
                    return

            #id assignation
            bind.meli_id = product.meli_id
            bind.meli_id_variation = product.meli_id_variation
            bind.conn_id = product.meli_id
            bind.conn_variation_id = product.meli_id_variation

            #TODO: sku assign?
            bind.sku = product.default_code
            bind.barcode = product.barcode

            #basic info
            bind.meli_title = product.meli_title
            bind.meli_description = product.meli_description
            bind.meli_category = product.meli_category
            bind.meli_price = product.meli_price
            bind.price = product.meli_price
            bind.stock = product.meli_available_quantity
            bind.meli_available_quantity = product.meli_available_quantity

            bind.meli_shipping_logistic_type = product.meli_shipping_logistic_type
            bind.meli_shipping_free = product.meli_shipping_free

            #attributes
            bind.meli_attributes = product.meli_attributes
            bind.meli_model = product.meli_model
            bind.meli_brand = product.meli_brand
            bind.meli_gender = bind.product_tmpl_id and bind.product_tmpl_id.meli_gender
            bind.meli_grid_chart_id = bind.product_tmpl_id and bind.product_tmpl_id.meli_grid_chart_id

            #publish ref info
            bind.meli_pub = product.meli_pub
            #bind.meli_master = product.meli_master
            #bind.meli_ids = product.meli_ids

            #config info
            bind.meli_currency = product.meli_currency
            bind.meli_condition = product.meli_condition
            bind.meli_warranty = product.meli_warranty
            bind.meli_listing_type = product.meli_listing_type
            bind.meli_dimensions = product.meli_dimensions

    def copy_from_rjson( self, rjson, meli=None ):
        #copia correctamente el sku correspondiente al conn_variation_id
        #conn_variation_id debe setearse al traer el producto ?
        _logger.info("variant bind >> copy_from_rjson")
        if not rjson:
            return

        for bind in self:
            account = bind.connection_account
            config = account.configuration
            #productT = bindT.product_tmpl_id
            #basic info
            catid, wwwid = self.env["mercadolibre.category"].meli_get_category( rjson['category_id'], meli=meli, create_missing_website=config.mercadolibre_create_website_categories )
            desplain = ("description" in rjson and rjson["description"]) or None
            seller_sku = None
            barcode = None
            variant_stock = 0
            if "variations" in rjson and len(rjson["variations"]):
                for var in rjson["variations"]:
                    if not "id" in var:
                        _logger.error(var)
                    if ("id" in var and str(var["id"]) == str(bind.conn_variation_id) ):
                        _logger.info("FOUNDED!!!")
                        seller_sku = ("seller_sku" in var and var["seller_sku"]) or ""
                        barcode = ("barcode" in var and var["barcode"]) or ""
                        variant_stock = ("available_quantity" in var and var["available_quantity"])
                    if (not bind.conn_variation_id):
                        if (len(rjson["variations"])==1):
                            seller_sku = ("seller_sku" in var and var["seller_sku"]) or None
                            barcode = ("barcode" in var and var["barcode"]) or None
                            variant_stock = ("available_quantity" in var and var["available_quantity"])
                            bind.conn_variation_id = str(var["id"])

                if not seller_sku:
                    _logger.error("seller sku not found: meli_id: "+str(bind.conn_id)+" varid: "+str(bind.conn_variation_id))
            if not seller_sku:
                seller_sku = ("seller_sku" in rjson and rjson["seller_sku"]) or ""
            if not barcode:
                barcode = ("barcode" in rjson and rjson["barcode"]) or ""
            fields = {
                'meli_permalink': rjson['permalink'],
                'meli_title': rjson['title'].encode("utf-8"),
                'meli_listing_type': rjson['listing_type_id'],
                'meli_buying_mode':rjson['buying_mode'],
                'meli_price': str(rjson['price']),
                'price': str(rjson['price']),
                'meli_available_quantity': variant_stock,
                'stock': variant_stock,
                'meli_currency': rjson['currency_id'],
                'meli_condition': rjson['condition'],
                #'meli_available_quantity': rjson['available_quantity'],
                'meli_warranty': rjson['warranty'],
                'meli_category': catid,
                'meli_id': rjson["id"],
                'sku': seller_sku or '',
                'barcode': barcode or '',
                'meli_id_variation': bind.conn_variation_id,
                #'meli_imagen_link': rjson['thumbnail'],
                #'meli_video': str(vid),
                #'meli_dimensions': meli_dim_str,
            }
            if desplain:

                #publication specific banner
                bindT = bind.binding_product_tmpl_id
                mlbanner = bindT and bindT.product_tmpl_id.meli_mercadolibre_banner
                #configuration banner
                mlbanner = mlbanner or (config and config.mercadolibre_banner)
                meli_description = ""
                if (mlbanner):
                    #get the text, not the header nor the footer
                    meli_description = mlbanner.get_from_ml_description( desplain )

                fields["meli_description"] = meli_description

            meli_shipping_logistic_type = ( rjson and "shipping" in rjson and "logistic_type" in rjson["shipping"] and rjson["shipping"]["logistic_type"] ) or ""
            meli_shipping_logistic_type and fields.update({'meli_shipping_logistic_type': meli_shipping_logistic_type })

            meli_shipping_free = ( rjson and "shipping" in rjson and "free_shipping" in rjson["shipping"] and rjson["shipping"]["free_shipping"] ) or False
            meli_shipping_free and fields.update({'meli_shipping_free': meli_shipping_free })

            _logger.info("variant bind >> copy_from_rjson: var id: "+str(fields["meli_id_variation"])+" sku: "+str(fields["sku"])+" barcode: "+str(fields["barcode"]) )
            bind.write(fields)

    def fetch_meli_product( self, meli = None, rjson = None, from_meli_oerp=False ):
        _logger.info("binding variant fetch_meli_product")

        #fetch product full data from MELI into binding
        for bind in self:

            account = bind.connection_account
            config = account and account.configuration
            meli_id = bind.conn_id
            meli_id_variation = bind.conn_variation_id

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            if not meli_id or not meli:
                continue;

            if from_meli_oerp: #TODO, check validity and meli_id in bindT.product_tmpl_id.meli_ids:
                bind.copy_from_meli_oerp()
            else:
                rjson = rjson or account.fetch_meli_product( meli_id=meli_id, meli=meli )
                bind.copy_from_rjson( rjson=rjson, meli=meli )

            if (config.mercadolibre_update_local_stock):
                product = bind.product_id
                _logger.info("product_update_stock: "+str(bind.stock))
                #_logger.info("product_update_stock: rjson: "+str(rjson))
                _logger.info("meli: "+str(meli))
                _logger.info("account: "+str(account))
                product and product.product_update_stock(stock=bind.stock, meli_id=meli_id, meli=meli, config=config )

    def update_pl_price( self, meli_price=meli_price):

        bind = self
        account = bind.connection_account
        config = account and account.configuration

        force_variant = False
        pli = self.env['product.pricelist.item']
        pli_tpl = False

        pl = bind.meli_pricelist
        product = bind.product_id
        product_template = product.product_tmpl_id

        if force_variant:
            pli_tpl = False
        else:
            pli_tpl = pli.search([('pricelist_id','in',[pl.id]),('product_tmpl_id','=',product_template.id)])

        ml_price_converted = product._meli_price_converted( meli_price=meli_price, config=config )

        pli_var = pli.search([('pricelist_id','in',[pl.id]),('product_id','=',product.id)])

        if (pli_tpl or pli_var):
            #_logger.info("Updating price")
            return_val = pl.price_get( product.id, 1.0 )
            if (pl.id in return_val):
                old_price = return_val[pl.id]
                if pli_tpl:
                    pli_tpl.write({'fixed_price': float(ml_price_converted)})
                if pli_var:
                    pli_var.write({'fixed_price': float(ml_price_converted)})
        else:
            _logger.info("Creating price")
            if force_variant and not pli_var:
                pli_var = pli.create({
                        'product_id': product.id,
                        'min_quantity': 0,
                        'applied_on': '0_product_variant',
                        'pricelist_id': pl.id,
                        'compute_price': 'fixed',
                        'currency_id': pl.currency_id.id,
                        'fixed_price': float(ml_price_converted)
                         })
            else:
                if not force_variant and not pli_tpl:
                    pli_tpl = pli.create({
                            'product_tmpl_id': product_template.id,
                            'min_quantity': 0,
                            'applied_on': '1_product',
                            'pricelist_id': pl.id,
                            'compute_price': 'fixed',
                            'currency_id': pl.currency_id.id,
                            'fixed_price': float(ml_price_converted)
                             })


    def update_price( self, meli_price=False, meli_pricelist=False, meli_price_fixed=False ):
        for bind in self:

            account = bind.connection_account
            config = account and account.configuration

            #Update variant product price
            product = bind.product_id
            product_tmpl = product and product.product_tmpl_id
            base_meli_price = product.set_meli_price(config=config)
            bindT = bind.binding_product_tmpl_id

            #set if manually set
            _logger.info("1 bind.meli_price: "+str(bind.meli_price))
            _logger.info("bindT.meli_price: "+str(bindT.meli_price))
            bind.meli_pricelist = meli_pricelist or bind.meli_pricelist or (bindT and bindT.meli_pricelist)
            bind.meli_price_fixed = meli_price_fixed or bind.meli_price_fixed or (bindT and bindT.meli_price_fixed)
            bind.meli_price = meli_price or (bindT and bindT.meli_price) or bind.meli_price
            _logger.info("2 bind.meli_price: "+str(bind.meli_price))

            #if price is fixed use binding price or if not, using odoo product pricing
            if bind.meli_price_fixed:
                bind.meli_price = bind.meli_price or bind.product_id.meli_price or bind.product_id.product_tmpl_id.meli_price
            elif not bind.meli_price_fixed:
                bind.meli_price = base_meli_price


            _logger.info("3 bind.meli_price: "+str(bind.meli_price))
            #price list is preferred if selected, always, but only if it's selected
            pl = bind.meli_pricelist
            #check binding currency based for USD
            pl = pl or (bind.meli_currency and bind.meli_currency in ["USD"] and config.mercadolibre_pricelist_usd and config.mercadolibre_pricelist_usd.currency_id.name=="USD" and config.mercadolibre_pricelist_usd)
            product = bind.product_id
            if pl and product:
                _logger.info("Pricelist:"+str(pl and pl.name)+" product:"+str(product.name)+" ["+str(product.default_code)+"]")
                #if manual set in pricelist
                if (meli_price):
                    bind.update_pl_price(meli_price=meli_price)
                #if not update from pricelist
                return_val = get_price_from_pl( pl, product, 1.0 )
                if pl.id in return_val:
                    new_price = return_val[pl.id]
                    #added taxes here
                    tax_excluded = ml_tax_excluded(self,config=config)
                    if ( tax_excluded and product_tmpl and product_tmpl.taxes_id ):
                        _logger.info("Adjust taxes for publish")
                        txfixed = 0
                        txpercent = 0
                        _logger.info("Adjust taxes")
                        for txid in product_tmpl.taxes_id:
                            if (txid.type_tax_use=="sale" and not txid.price_include):
                                if (txid.amount_type=="percent"):
                                    txpercent = txpercent + txid.amount
                                if (txid.amount_type=="fixed"):
                                    txfixed = txfixed + txid.amount
                        if (txfixed>0 or txpercent>0):
                            #_logger.info("Tx Total:"+str(txtotal)+" to Price:"+str(ml_price_converted))
                            new_price = txfixed + new_price * (1.0 + txpercent*0.01)

                    _logger.info("Price adjusted:"+str(new_price))

                    if (new_price>0):
                        bind.meli_price = new_price

            bind.meli_price = round(float(bind.meli_price),2)

            if (product_tmpl.meli_currency and (product_tmpl.meli_currency == 'MXN' or product_tmpl.meli_currency == 'USD')):
                bind.meli_price = str((float(bind.meli_price)))
            elif (product_tmpl.meli_currency and product_tmpl.meli_currency == 'CLP'):
                bind.meli_price = str( int( int( math.floor(int(bind.meli_price) / 100 ) * 100 + 90 ) ) )
            else:
                bind.meli_price = math.ceil(float(bind.meli_price))
                bind.meli_price = str(int(float(bind.meli_price)))

            _logger.info("update_price meli_price (forced?): "+str(meli_price))
            _logger.info("update_price bind.meli_price: "+str(bind.meli_price))
            _logger.info("update_price bind.meli_pricelist: "+str(bind.meli_pricelist))
            _logger.info("update_price bind.meli_price_fixed: "+str(bind.meli_price_fixed))

            bind.price = bind.meli_price

            bind._onchange_meli_price()


    def product_post( self, meli=None ):
        _logger.info("MercadoLibre Bind Product Post")
        result = []
        for bind in self:

            product = bind.product_id
            account = bind.connection_account
            meli_id = bind.conn_id
            meli_id_variation = bind.conn_variation_id
            bind_tpl = bind.binding_product_tmpl_id

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            if not meli_id or not meli:
                continue;

            if product:
                res = product.product_post( bind_tpl=bind_tpl, bind=bind, meli=meli, config=account.configuration )
                result.append(res)
        _logger.info( "result: " + str(result) )
        return result

    def product_update( self ):
        _logger.info("meli_oerp_multiple >> MercadoLibre Product Binding Update")

    #def category_predictor( self ):
    #    _logger.info("MercadoLibre Product template Category Predictor")
    def product_meli_get_product( self, meli=None, rjson=None ):

        _logger.info("meli_oerp_multiple >> product_meli_get_product >> (Binding) MercadoLibre Product product_meli_get_product: "+str(meli))
        _logger.info(str(rjson))
        for bind in self:

            account = bind.connection_account
            product = bind.product_id
            product_template = bind.product_tmpl_id
            meli_id = bind.conn_id
            meli_id_variation = bind.conn_variation_id

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            rjson = rjson or account.fetch_meli_product( meli_id=meli_id, meli=meli )
            #is this binding the master odoo product meli id?
            meli_oerp_match_import = (product.meli_id and meli_id and product.meli_id==meli_id)
            #just bind, never import
            bind_only = (meli_oerp_match_import==False)
            #TODO: recheck to not import ML to Odoo Product if this is not the principal bind conn_id
            if (not product.meli_id or meli_oerp_match_import):
                _logger.info("product_meli_get_product: meli_oerp_match_import:" + str(meli_oerp_match_import) +" bind_only: "+str(bind_only))
                res = product.product_meli_get_product( meli_id=meli_id, account=account, meli=meli, rjson=rjson )
                _logger.info("variant get product >> product_meli_get_product res:"+str(res))
                if res and "error" in res:
                    _logger.error(res)
                    return res

            #TODO: recheck bindings for this product and this binding
            if (product_template):
                bindT = product_template.mercadolibre_bind_to( account=account, meli_id=meli_id, bind_variants=True, meli=meli, rjson=rjson, bind_only=bind_only )
                if bindT:
                    # from_meli_oerp = True copy form recent imported
                    bindT.fetch_meli_product( meli=meli, from_meli_oerp=False, fetch_variants=True, rjson=rjson )

    def action_category_predictor( self ):
        _logger.info("MercadoLibre Product action_category_predictor")

    #VARIANT binding product_post_stock
    def product_post_stock( self, context=None, meli=None, optimize=False ):
        #_logger.info("MercadoLibre Product product_post_stock: context: "+str(context)+" meli: "+str(meli)+" optimize:"+str(optimize))
        for bindv in self:
            bindv._meli_stock_status()
            account = bindv.connection_account
            config = account and account.configuration
            product = bindv.product_id
            product_template = bindv.product_tmpl_id or (product and product.product_tmpl_id)
            meli_id = bindv.conn_id
            meli_id_variation = bindv.conn_variation_id
            bindT = bindv.binding_product_tmpl_id

            if bindT.meli_update_stock_blocked or product.meli_update_stock_blocked or product_template.meli_update_stock_blocked:
                continue;

            if not product or not product_template or not product.active or not product_template.active:
                _logger.error("bindv > product_post_stock > Product Binded not active or missing! "+str(product and product.name)+" tpl:"+str(product_template and product_template.name))
                if not product.active or not product_template.active:
                    _logger.error("bindv > product_post_stock > Product Binded not active")
                continue;

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            #
            try:
                #_logger.info("mercadolibre.product product_post_stock")
                res = {}
                #one variant bind from variant product
                bindv.meli_available_quantity = product._meli_available_quantity( meli_id=meli_id, meli=meli, config=config)
                bindv.stock = bindv.meli_available_quantity
                #if bindv.meli_inventory_id and bindv.product_id and bindv.product_id.active:
                if bindv.product_id and bindv.product_id.active:
                    logistic_type = bindv.product_id._meli_update_logistic_type(meli_id=meli_id, meli=meli,config=config)
                    if logistic_type and logistic_type in ["fulfillment"]:
                        bindv.stock_update = ml_datetime( str( datetime.now() ) )
                        res = { "error": "fulfillment"}
                        bindv.stock_error = str(res)
                        bindv.stock_update = ml_datetime( str( datetime.now() ) )
                        bindv._meli_stock_status()
                        bindT.stock_update = bindv.stock_update
                        bindT.stock_error = bindv.stock_error
                        #_logger.info(bindv.stock_error)
                        rjson = account.fetch_meli_product(meli_id=meli_id,meli=meli)
                        if bindv.stock<=0:
                            stock_total = rjson and rjson["available_quantity"]
                            if stock_total and stock_total>0 and bindv.meli_status not in ['active']:
                                _logger.info("bindv > product_post_stock > fulfillment Activate!")
                                bindv.product_meli_status_active(meli=meli)

                        if rjson and "variations" in rjson and len(rjson["variations"]):
                            for var in rjson["variations"]:
                                for bv in bindT.variant_bindings:
                                    if bv.conn_variation_id == "id" in var and var["id"]:
                                        bv.stock = var["available_quantity"]
                                        bv.meli_available_quantity = var["available_quantity"]

                        if bindv.stock>0 and bindv.meli_status not in ['active']:
                            _logger.info("bindv > product_post_stock > fulfillment Activate!")
                            bindv.product_meli_status_active(meli=meli)
                        return res
                if bindv.product_id and not bindv.product_id.active:
                    res = { "error": "product archived"}
                    bindv.stock_error = str(res)
                    bindv.stock_update = ml_datetime( str( datetime.now() ) )
                    bindT.stock_update = bindv.stock_update
                    bindT.stock_error = bindv.stock_error
                    _logger.error(bindv.stock_error)
                    return res
                if not bindv.product_id:
                    res = { "error": "no product binded"}
                    bindv.stock_error = str(res)
                    bindv.stock_update = ml_datetime( str( datetime.now() ) )
                    bindv._meli_stock_status()
                    bindT.stock_update = bindv.stock_update
                    bindT.stock_error = bindv.stock_error
                    _logger.error(bindv.stock_error)
                    return res

                post_stock = True
                is_pub_as_variant_ok = True
                if (optimize):
                    #avoid posting when pub_as_variant
                    is_pub_as_variant_ok = product_template.meli_pub_as_variant and product_template.meli_pub_principal_variant
                    is_pub_as_variant_ok = is_pub_as_variant_ok and (product_template.meli_pub_principal_variant.id==bindv.product_id.id)
                    post_stock = is_pub_as_variant_ok

                if (post_stock or is_pub_as_variant_ok):
                    res = product.x_product_post_stock( context=context, meli=meli, config=config,
                                                        meli_id=meli_id, meli_id_variation=meli_id_variation,
                                                        target=bindv )
                if res and 'error' in res:
                    #if 'fulfillment' in str(res):
                    #    bindv.meli_inventory_id = "fetch"
                    bindv.stock_error = str(res)
                    bindv.stock_update = ml_datetime( str( datetime.now() ) )
                    bindv._meli_stock_status()
                    bindT.stock_update = bindv.stock_update
                    bindT.stock_error = bindv.stock_error
                    return res
                #bindv.meli_inventory_id = None
                #more than one
                bindv.stock_error = "Ok"
                bindv.stock_update = ml_datetime( str( datetime.now() ) )
                bindv._meli_stock_status()
                bindT.stock_update = bindv.stock_update
                bindT.stock_error = bindv.stock_error

                #TODO
                stock = 0
                stock_error = ""
                for bindvariant in bindT.variant_bindings:
                    stock+= (bindvariant.stock or bindvariant.meli_available_quantity)
                    stock_error+= str(bindvariant.stock_error)
                bindT.stock = stock

            except Exception as e:
                _logger.info("mercadolibre.product product_post_stock > exception error")
                _logger.info(e, exc_info=True)
                bindv.stock_error = str(e)
                bindv.stock_update = ml_datetime( str( datetime.now() ) )
                bindv._meli_stock_status()

                bindT.stock_update = bindv.stock_update
                bindT.stock_error = bindv.stock_error
                pass;

            return {}

    def product_post_price( self, context=None, meli=None ):
        _logger.info("MercadoLibre Product product_post_price: context: "+str(context)+" self:"+str(self))
        for bindv in self:

            account = bindv.connection_account
            config = account and account.configuration
            product = bindv.product_id
            product_template = bindv.product_tmpl_id or (product and product.product_tmpl_id)
            meli_id = bindv.conn_id
            meli_id_variation = bindv.conn_variation_id
            bindT = bindv.binding_product_tmpl_id

            if not product or not product_template:
                _logger.error("product_template:"+str(product_template)+" product:"+str(product))
                continue;

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account )

            #
            try:
                _logger.info("mercadolibre.product product_post_price: price:"+str(bindv.price)+" meli_price: "+str(bindv.meli_price))
                #one variant bind from variant product

                #if not bindv.meli_price:
                #    bindv.meli_price = base_meli_price
                #else:
                #    bindv.meli_price = (not bindv.meli_price_fixed and base_meli_price) or bindv.meli_price
                #bindv.price = bindv.meli_price

                bindv.update_price()
                meli_currency = bindv.meli_currency or bindT.meli_currency

                _logger.info("mercadolibre.product product_post_price: bindv.price:"+str(bindv.price)+" meli_price: "+str(bindv.meli_price))
                res = product.x_product_post_price( context=context, meli_price=bindv.meli_price, meli_currency=meli_currency, meli=meli, config=config, meli_id=meli_id, meli_id_variation=meli_id_variation )
                if res and 'error' in res:
                    bindv.price_update = ml_datetime( str( datetime.now() ) )
                    return res
                bindv.price_update = ml_datetime( str( datetime.now() ) )
                #more than one

            except Exception as e:
                _logger.info("mercadolibre.product product_post_stock > exception error")
                _logger.info(e, exc_info=True)
                pass;

            return {}

    def product_meli_status_put( self, context=None, status=None, meli=False):

        company = self.env.user.company_id
        account = self.connection_account
        config = (account and account.configuration) or company
        company = ("company_id" in config._fields and config.company_id) or company

        meli_id = self.conn_id
        if not meli:
            meli = self.env['meli.util'].get_new_instance(company, account)

            if meli.need_login():
                return meli.redirect_login()

        if meli_id and status and (status in ['paused','closed','active']):
            response = meli.put("/items/"+str(meli_id), { 'status': status }, {'access_token':meli.access_token})
            if response:
                _logger.info(response.json())
        else:
            _logger.error("Undefined status set, meli_id: "+str(meli_id)+" status: "+str(status))
        return {}

    def product_meli_status_close( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product product_meli_status_close")
        return self.product_meli_status_put(context=context,status='closed',meli=meli)

    def product_meli_status_pause( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product product_meli_status_pause")
        for bindv in self:
            bindT = bindv.binding_product_tmpl_id
            bindT.product_meli_block()

        return self.product_meli_status_put(context=context,status='paused',meli=meli)

    def product_meli_status_active( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product product_meli_status_active")
        for bindv in self:
            bindT = bindv.binding_product_tmpl_id
            bindT.product_meli_unblock()
        return self.product_meli_status_put(context=context,status='active',meli=meli)

    def product_meli_delete( self, context=None, meli=False ):
        _logger.info("MercadoLibre Product product_meli_delete")
        company = self.env.user.company_id
        account = self.connection_account
        config = (account and account.configuration) or company
        company = ("company_id" in config._fields and config.company_id) or company

        meli_id = self.conn_id

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company, account)
        if meli.need_login():
            return meli.redirect_login()

        if meli_id:
            response = meli.put("/items/"+str(meli_id), { 'deleted': 'true' }, {'access_token':meli.access_token})

            rjson = response.json()
            _logger.info( rjson )
            ML_status = rjson["status"]
            if "error" in rjson:
                ML_status = rjson["error"]
            if "sub_status" in rjson:
                if len(rjson["sub_status"]) and rjson["sub_status"][0]=='deleted':
                    #product.write({ 'meli_id': '','meli_id_variation': '' })
                    _logger.info("Deleted ok: TODO: Delete variant binding, and meli_id on base product...")

        return {}

    def product_meli_upload_image( self ):
        _logger.info("MercadoLibre Product product_meli_upload_image")

    def product_meli_login( self ):
        _logger.info("MercadoLibre Product product_meli_login")

    def _update_sale_terms( self, meli, productjson ):

        bind = self

        product = bind.product_id

        terms = []

        if product:
            terms = product._update_sale_terms( meli=meli, productjson=productjson )

        return terms

    @api.onchange('name')
    def _change_meli_title(self):
        for b in self:
            b.meli_title = b.name
            #change all
            bt = b.binding_product_tmpl_id
            if bt:
                bt.name = b.name
                bt.meli_title = bt.name
                for bb in bt.variant_bindings:
                    bb.name = bt.name
                    bb.meli_title = bt.meli_title

    @api.depends('name')
    def change_meli_title(self):
        for b in self:
            b.meli_title = b.name
            #change all
            bt = b.binding_product_tmpl_id
            if bt:
                bt.name = b.name
                bt.meli_title = bt.name
                for bb in bt.variant_bindings:
                    bb.name = bt.name
                    bb.meli_title = bt.meli_title

class MercadoLibreConnectionBindingSaleOrderPayment(models.Model):

    _name = "mercadolibre.payment"
    _description = "MercadoLibre Sale Order Payment Binding"
    _inherit = ["ocapi.binding.payment","mercadolibre.payments"]

    order_id = fields.Many2one("mercadolibre.sale_order",string="Order")
    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )
    name = fields.Char(string="Payment Name")

    meli_oerp_payment = fields.Many2one( "mercadolibre.payments",string="Payment from meli_oerp")

    def _get_ml_journal(self):
        journal_id = None
        #journal_id = self.env.user.company_id.mercadolibre_process_payments_journal
        #if not journal_id:
        #    journal_id = self.env['account.journal'].search([('code','=','ML')])
        #if not journal_id:
        #    journal_id = self.env['account.journal'].search([('code','=','MP')])
        return journal_id

    def _get_ml_partner(self):
        partner_id = None
        #partner_id = self.env.user.company_id.mercadolibre_process_payments_res_partner
        #if not partner_id:
        #    partner_id = self.env['res.partner'].search([('ref','=','MELI')])
        #if not partner_id:
        #    partner_id = self.env['res.partner'].search([('name','=','MercadoLibre')])
        return partner_id

    def _get_ml_customer_partner(self):
        sale_order = self._get_ml_customer_order()
        return (sale_order and sale_order.partner_id)

    def _get_ml_customer_order(self):
        mlorder = self.order_id
        mlshipment = mlorder.shipment
        return (mlorder and mlorder.sale_order) or (mlshipment and mlshipment.sale_order)

    def create_payment(self):
        self.ensure_one()
        if self.account_payment_id:
            raise ValidationError('Ya esta creado el pago')
        if self.status != 'approved':
            return None
        journal_id = self._get_ml_journal()
        payment_method_id = self.env['account.payment.method'].search([('code','=','electronic'),('payment_type','=','inbound')])
        if not journal_id or not payment_method_id:
            raise ValidationError('Debe configurar el diario/metodo de pago')
        partner_id = self._get_ml_customer_partner()
        currency_id = self.env['res.currency'].search([('name','=',self.currency_id)])
        if not currency_id:
            raise ValidationError('No se puede encontrar la moneda del pago')

        communication = self.payment_id
        if self._get_ml_customer_order():
            communication = ""+str(self._get_ml_customer_order().name)+" OP "+str(self.payment_id)+str(" TOT")

        vals_payment = {
                'partner_id': partner_id.id,
                'payment_type': 'inbound',
                'payment_method_id': payment_method_id.id,
                'journal_id': journal_id.id,
                'meli_payment_id': self.id,
                'communication': communication,
                'currency_id': currency_id.id,
                'partner_type': 'customer',
                'amount': self.total_paid_amount,
                }
        acct_payment_id = self.env['account.payment'].create(vals_payment)
        acct_payment_id.post()
        self.account_payment_id = acct_payment_id.id

    def create_supplier_payment(self):
        self.ensure_one()
        if self.status != 'approved':
            return None
        if self.account_supplier_payment_id:
            raise ValidationError('Ya esta creado el pago')
        journal_id = self._get_ml_journal()
        payment_method_id = self.env['account.payment.method'].search([('code','=','outbound_online'),('payment_type','=','outbound')])
        if not journal_id or not payment_method_id:
            raise ValidationError('Debe configurar el diario/metodo de pago')
        partner_id = self._get_ml_partner()
        if not partner_id:
            raise ValidationError('No esta dado de alta el proveedor MercadoLibre')
        currency_id = self.env['res.currency'].search([('name','=',self.currency_id)])
        if not currency_id:
            raise ValidationError('No se puede encontrar la moneda del pago')

        communication = self.payment_id
        if self._get_ml_customer_order():
            communication = ""+str(self._get_ml_customer_order().name)+" OP "+str(self.payment_id)+str(" FEE")

        vals_payment = {
                'partner_id': partner_id.id,
                'payment_type': 'outbound',
                'payment_method_id': payment_method_id.id,
                'journal_id': journal_id.id,
                'meli_payment_id': self.id,
                'communication': communication,
                'currency_id': currency_id.id,
                'partner_type': 'supplier',
                'amount': self.fee_amount,
                }
        acct_payment_id = self.env['account.payment'].create(vals_payment)
        acct_payment_id.post()
        self.account_supplier_payment_id = acct_payment_id.id

    def create_supplier_payment_shipment(self):
        self.ensure_one()
        if self.status != 'approved':
            return None
        if self.account_supplier_payment_shipment_id:
            raise ValidationError('Ya esta creado el pago')
        journal_id = self._get_ml_journal()
        payment_method_id = self.env['account.payment.method'].search([('code','=','outbound_online'),('payment_type','=','outbound')])
        if not journal_id or not payment_method_id:
            raise ValidationError('Debe configurar el diario/metodo de pago')
        partner_id = self._get_ml_partner()
        if not partner_id:
            raise ValidationError('No esta dado de alta el proveedor MercadoLibre')
        currency_id = self.env['res.currency'].search([('name','=',self.currency_id)])
        if not currency_id:
            raise ValidationError('No se puede encontrar la moneda del pago')
        if (not self.order_id or not self.order_id.shipping_list_cost>0.0):
            raise ValidationError('No hay datos de costo de envio')

        communication = self.payment_id
        if self._get_ml_customer_order():
            communication = ""+str(self._get_ml_customer_order().name)+" OP "+str(self.payment_id)+str(" SHP")

        vals_payment = {
                'partner_id': partner_id.id,
                'payment_type': 'outbound',
                'payment_method_id': payment_method_id.id,
                'journal_id': journal_id.id,
                'meli_payment_id': self.id,
                'communication': communication,
                'currency_id': currency_id.id,
                'partner_type': 'supplier',
                'amount': self.order_id.shipping_list_cost,
                }
        acct_payment_id = self.env['account.payment'].create(vals_payment)
        acct_payment_id.post()
        self.account_supplier_payment_shipment_id = acct_payment_id.id

class MercadoLibreConnectionBindingSaleOrderShipmentItem(models.Model):

    _name = "mercadolibre.bind_shipment.item"
    _description = "Ocapi Sale Order Shipment Item"
    _inherit = ["ocapi.binding.shipment.item", "mercadolibre.shipment.item"]

    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )
    shipping_id = fields.Many2one("mercadolibre.bind_shipment",string="Shipment Binding")
    product = fields.Char(string="Product Id")
    variation = fields.Char(string="Variation Id Binded")
    quantity = fields.Float(string="Quantity")

class MercadoLibreConnectionBindingSaleOrderShipment(models.Model):

    _name = "mercadolibre.bind_shipment"
    _description = "Ocapi Sale Order Shipment Binding"
    _inherit = ["ocapi.binding.shipment","mercadolibre.shipment"]

    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )

    order_id = fields.Many2one("mercadolibre.sale_order",string="Order Id")
    products = fields.One2many("mercadolibre.bind_shipment.item", "shipping_id", string="Product Items")

class MercadoLibreConnectionBindingSaleOrderClient(models.Model):

    _name = "mercadolibre.client"
    _description = "MercadoLibre Client Binding"
    _inherit = ["ocapi.binding.client","mercadolibre.buyers"]

    def get_display_name(self):
        for client in self:
            client.display_name = str(client.contactPerson)+" ["+str(client.name)+"]"

    display_name = fields.Char(string="Display Name",store=False,compute=get_display_name)
    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )

class MercadoLibreConnectionBindingSaleOrderLine(models.Model):

    _name = "mercadolibre.sale_order_line"
    _description = "MercadoLibre Sale Order Line Binding"
    _inherit = ["ocapi.binding.sale_order_line", "mercadolibre.order_items" ]

    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )
    order_id = fields.Many2one("mercadolibre.sale_order",string="Order")

class MercadoLibreConnectionBindingSaleOrder(models.Model):

    _name = "mercadolibre.sale_order"
    _description = "MercadoLibre Sale Order Binding Sale"
    _inherit = ["ocapi.binding.sale_order","mercadolibre.orders"]

    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )
    mercadolibre_old_order = fields.Many2one( "mercadolibre.orders", string="MercadoLibre Old Order" )
    client = fields.Many2one("mercadolibre.client",string="Client",index=True)

    lines = fields.One2many("mercadolibre.sale_order_line","order_id", string="Order Items")
    payments = fields.One2many("mercadolibre.payment","order_id",string="Order Payments")
    shipments = fields.One2many("mercadolibre.bind_shipment","order_id",string="Order Shipments")


    def orders_query_iterate( self, offset=0, account=None, meli=None, context=None ):

        offset_next = 0

        account = account or self.connection_account
        company = (account and account.company_id) or self.env.user.company_id
        config = account.configuration or company
        context = context or self.env.context

        orders_obj = self.env['mercadolibre.sale_order']

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company, account)

        orders_query = "/orders/search?seller="+meli.seller_id+"&sort=date_desc"
        #TODO: "create parameter for": orders_query+= "&limit=10"

        if (offset):
            orders_query = orders_query + "&offset="+str(offset).strip()

        response = meli.get( orders_query, {'access_token':meli.access_token})
        orders_json = response.json()

        if "error" in orders_json:
            _logger.error( orders_query )
            _logger.error( orders_json["error"] )
            if (orders_json["message"]=="invalid_token"):
                _logger.error( orders_json["message"] )
            return {}

        order_date_filter = ("mercadolibre_filter_order_datetime" in config._fields and config.mercadolibre_filter_order_datetime)

        if "paging" in orders_json:
            if "total" in orders_json["paging"]:
                if (orders_json["paging"]["total"]==0):
                    return {}
                else:
                    if (orders_json["paging"]["total"]>=(offset+orders_json["paging"]["limit"])):
                        if not order_date_filter:
                            offset_next = 0
                        else:
                            offset_next = offset + orders_json["paging"]["limit"]
                        _logger.info("offset_next:"+str(offset_next))

        if "results" in orders_json:
            for order_json in orders_json["results"]:
                if order_json:
                    #_logger.info( order_json )
                    pdata = {"id": False, "order_json": order_json}
                    try:
                        self.orders_update_order_json( data=pdata, config=config, meli=meli )
                        self._cr.commit()
                    except Exception as e:
                        _logger.error("orders_query_iterate > Error actualizando ORDEN")
                        _logger.error(e, exc_info=True)
                        pass

        if (offset_next>0):
            self.orders_query_iterate(offset=offset_next, account=account, meli=meli)

        return {}

    def orders_query_recent( self, account=None, meli=None, context=None ):

        context = context or self.env.context
        account = account or self.connection_account

        _logger.info("mercadolibre.sale_order >> orders_query_recent("+str(account)+","+str(meli)+") context: " + str(context))
        if not account:
            return {}

        company = (account and account.company_id) or self.env.user.company_id
        config = account.configuration or company

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company, account)

        if 1==1:
            _logger.info("mercadolibre.sale_order >> recall mercadolibre.orders >> orders_query_recent: "+str(config and config.name))
            self.env['mercadolibre.orders'].orders_query_recent( meli=meli, config=config )
            return {}

        Autocommit( self )

        try:
            self.orders_query_iterate( offset=0, account=account, meli=meli )
        except Exception as e:
            _logger.info("orders_query_recent > Error iterando ordenes")
            _logger.error(e, exc_info=True)
            self._cr.rollback()

        return {}

#class MercadoLibreConnectionBindingProductCategory(models.Model):

#    _name = "mercadolibre.category"
#    _description = "MercadoLibre Binding Category"
#    _inherit = "ocapi.binding.category"

#    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )

#    name = fields.Char(string="Category",index=True)
#    category_id = fields.Char(string="Category Id",index=True)
