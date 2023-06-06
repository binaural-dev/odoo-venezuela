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
from odoo.addons.meli_oerp.models.warning import warning
import requests

from odoo.addons.meli_oerp.models.versions import *

from . import versions
from .versions import *

from odoo.exceptions import UserError, ValidationError

import hashlib
import math
import base64
import mimetypes
from urllib.request import urlopen
import string
if (not ('replace' in string.__dict__)):
    string = str

class product_template(models.Model):

    _inherit = "product.template"

    mercadolibre_bindings = fields.Many2many( "mercadolibre.product_template", string="MercadoLibre Connection Bindings", copy=False )

    def ocapi_price(self, account):
        return self.lst_price

    def ocapi_stock(self, account):
        return self.virtual_available

    def mercadolibre_image_url_principal(self):
        return "/ocapi/mercadolibre/img/%s/%s/%s" % (str(self.id), str(self.default_code), str("default") )

    def mercadolibre_image_id_principal(self):
        return "%s" % ( str(self.id) )

    def mercadolibre_image_url(self, image):
        return "/ocapi/mercadolibre/img/%s/%s/%s" % (str(self.id), str(self.default_code), str(image.id) )

    def mercadolibre_image_id(self, image):
        return "%s" % ( str(image.id) )

    # Binding template
    # @param account
    # @param meli_id (meli_id to bind the product.template to, fetch the meli_id publication to check ids validaty too)
    # @param bind_variant (set with product.product to bind specific variant)
    # @param bind_variants (set to bind all variants to Producteca, if meli_id exists fetchs meli ids and id variations)
    # @param meli (set to optimize access to meli api (account specific))
    # @param bind_only (do not bind blindly, just make the binding using SKU reference and such)
    def mercadolibre_bind_to( self, account, meli_id = None, rjson=None, bind_variants = True, bind_variant=None, meli=None, bind_only=False ):

        pt_bind = None
        account_id = (account and type(account)!=int and account.id) or (type(account)==int and account)
        account = self.env["mercadolibre.account"].browse(account_id)
        _logger.info("product_template > mercadolibre_bind_to > "+" context:"+str(self.env.context)+" account_id:"+str(account_id) + " account:"+str(account.name) )
        for product_tmpl_id in self:

            for bind in product_tmpl_id.mercadolibre_bindings:
                if ( account_id in bind.connection_account.ids):
                    #account ok, now check if conn_id/meli_id is ok.
                    if ( bind.conn_id == meli_id ):
                        _logger.info("No need to add")
                        continue;

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account)

            if rjson or meli_id:
                #if meli is not set, its a new pub or a new bind
                rjson = rjson or account.fetch_meli_product( meli_id = meli_id, meli=meli )

            meli_title = rjson and "title" in rjson and rjson["title"].encode("utf-8")
            meli_title = meli_title or product_tmpl_id.meli_title or product_tmpl_id.name

            _logger.info(_("mercadolibre_bind_to >> Adding/Update product (tpl) %s to %s, id: %s, bind_variants: %i") % (product_tmpl_id.display_name, account.name, str(meli_id), bind_variants))
            try:
                prod_binding = {
                    "connection_account": account.id,
                    "product_tmpl_id": product_tmpl_id.id,
                    "name": meli_title,
                    "meli_title": meli_title,
                    "description": product_tmpl_id.description_sale,
                    "sku": product_tmpl_id.product_variant_ids.mapped("default_code") or product_tmpl_id.default_code or '',
                    "barcode": product_tmpl_id.product_variant_ids.mapped("barcode") or product_tmpl_id.barcode or '',
                    "conn_id": meli_id,
                    #"meli_id": meli_id,
                    #"meli_id": meli_id or None
                    #"price": product.ocapi_price(account),
                    #"stock": product.ocapi_stock(account),
                }
                pt_bind = self.env["mercadolibre.product_template"].search([ ("product_tmpl_id","=",product_tmpl_id.id),
                                                                             ("connection_account","=",account.id),
                                                                             ("conn_id", "=", meli_id)])
                if len(pt_bind):
                    pt_bind = pt_bind[0]
                    self.env["mercadolibre.product_template"].write([prod_binding])
                else:
                    pt_bind = self.env["mercadolibre.product_template"].create([prod_binding])

                if pt_bind:
                    pt_bind.copy_from_rjson( rjson=rjson, meli=meli )

                    product_tmpl_id.mercadolibre_bindings = [(4, pt_bind.id)]
                    if (bind_variants or bind_variant):
                        _logger.info( "[PRODUCT.TEMPLATE] mercadolibre_bind_to > Binding Variants X "+str(len(product_tmpl_id.product_variant_ids)) )
                        vari = 0
                        has_variations = False
                        for variant in product_tmpl_id.product_variant_ids:
                            vari+= 1
                            _logger.info( "[PRODUCT.TEMPLATE] mercadolibre_bind_to > Binding Variant: #"+str(vari))
                            if (bind_variant and bind_variant.id==variant.id):
                                _logger.info( "[PRODUCT.TEMPLATE] mercadolibre_bind_to [one variant] > Binding [PRODUCT.PRODUCT] Variant "+str(variant.display_name)+" bind_only: " + str(bind_only) )
                                pv_bind = variant.mercadolibre_bind_to( account, binding_product_tmpl_id=pt_bind, meli_id=meli_id, meli=meli, rjson=rjson, bind_only=bind_only )
                            elif (bind_variants and not bind_variant):
                                _logger.info( "[PRODUCT.TEMPLATE] mercadolibre_bind_to [all variants]> Binding [PRODUCT.PRODUCT] Variant "+str(variant.display_name)+" bind_only: " + str(bind_only) )
                                pv_bind = variant.mercadolibre_bind_to( account, binding_product_tmpl_id=pt_bind, meli_id=meli_id, meli=meli, rjson=rjson, bind_only=bind_only )

                            if (pv_bind and pv_bind.conn_variation_id):
                                has_variations = True
                        #DROP UNASSIGNED variation_ids
                        #is multi variation binding, but old bindings must not persist if conn_variation_id not set
                        if (has_variations or (pt_bind.variant_bindings and len(pt_bind.variant_bindings)>len(product_tmpl_id.product_variant_ids))):
                            #drop all UNASSIGNED bindings for this meli_id_variation
                            un_pv_bind = self.env["mercadolibre.product"].search([ ("conn_id","=",meli_id),
                                                                                ("conn_variation_id","=",False),
                                                                                ("product_tmpl_id","=",product_tmpl_id.id),
                                                                                ("connection_account","=",account.id)])
                            if un_pv_bind:
                                pvba = None
                                for pvb in un_pv_bind:
                                    pvba = pvb
                                    if pvba:
                                        _logger.info("Unlink UNASSIGNED conn_variation_id")
                                        pvba.unlink()

            except Exception as e:
                _logger.error(e, exc_info=True)

        return pt_bind

    def mercadolibre_unbind_from( self, account, meli_id=None, unbind_variants=True):
        pt_bind = None

        for productT in self:

            for bind in productT.mercadolibre_bindings:
                if not (account.id in bind.connection_account.ids):
                    _logger.info("No need to remove")
                    continue;

            _logger.info(_("Removing product %s to %s") % (productT.display_name, account.name))
            try:
                meli_id_filter = []
                if meli_id:
                    meli_id_filter = [( 'conn_id', '=', meli_id )]
                else:
                    meli_id_filter = [( 'conn_id', '=', None )]
                pt_binds = self.env["mercadolibre.product_template"].search( [("product_tmpl_id","=",productT.id),
                                                                             ("connection_account","=",account.id)]
                                                                             + meli_id_filter)
                for pt_bind in pt_binds:
                    if pt_bind:
                        productT.mercadolibre_bindings = [(3, pt_bind.id)]

                        if (unbind_variants):
                            for variant in productT.product_variant_ids:
                                pv_bind = variant.mercadolibre_unbind_from( account, binding_product_tmpl_id=pt_bind )

                        pt_bind.unlink()
            except Exception as e:
                _logger.error(e, exc_info=True)

        return pt_bind

    def product_template_update( self, meli_id=None, meli=None, account=None ):
        _logger.info("product.template >> product_template_update meli_id: "+str(meli_id)+" account: "+str(account)+" meli: "+str(meli))
        res = {}
        for productT in self:
            if not productT.mercadolibre_bindings:
                #bind and continue
                _logger.info("bind and continue: "+str(meli))
                productT.mercadolibre_bind_to( account=account, meli_id=meli_id, meli=meli )

            for bindT in productT.mercadolibre_bindings:
                _logger.info("Update bindings: bindT:"+str(bindT))
                res = bindT.product_template_update( meli=meli )
                if 'name' in res:
                    return res

        return res

    # Post product and bind them if needed
    # WARNING: the meli_oerp_multiple version always call the mercadolibre.product_template (bindings) method: product_template_post

    # @param meli_id if False try to post as a new ML post
    #                if MLABBBBBBB try to post/update the specific product itself
    def product_template_post( self, context=None, meli_id=None, meli=None, account=None ):

        context = context or self.env.context
        new_pub = context.get("force_meli_new_pub")
        _logger.info("product.template >> product_template_post context: "+str(context)+" meli_id: "+str(meli_id)+" account: "+str(account)+" new_pub: "+str(new_pub))


        res = {}
        for productT in self:
            #POST NEW
            _logger.info( "productT.mercadolibre_bindings:" + str(productT.mercadolibre_bindings) )
            if ((not productT.mercadolibre_bindings) or new_pub):
                #bind and continue post (meli_id defined or None(new pub))
                _logger.info("[PRODUCT.TEMPLATE] >> product_template_post > NEW PUBLICATION")

                if new_pub:
                    meli_id = None
                    _logger.info("Creating new pub")
                elif not productT.mercadolibre_bindings:
                    if productT.meli_pub_as_variant:
                        _logger.info("Auto binding old pub and update it")
                        autocorrect_principal = productT.meli_pub_principal_variant and productT.meli_pub_principal_variant.product_tmpl_id.id!=productT.id
                        if (autocorrect_principal):
                            productT.meli_pub_principal_variant = (productT.product_variant_ids and productT.product_variant_ids[0]) or None

                        meli_id = (productT.meli_pub_principal_variant and productT.meli_pub_principal_variant.meli_id) or None

                        _logger.info("Auto binding old pub and update it: 1st, meli_id: "+str(meli_id))
                        for variant in productT.product_variant_ids:
                            if variant.meli_id:
                                _logger.info("Auto binding old pub and update it: variant.meli_id: "+str(variant.meli_id))
                                meli_id = meli_id or variant.meli_id
                        _logger.info("Auto binding old pub and update it: Last, meli_id: "+str(meli_id))

                if productT.meli_pub_as_variant:
                    #create new binding template
                    bindT = productT.mercadolibre_bind_to( account=account, meli_id=meli_id, meli=meli )
                    #WARNING: TODO: new pub have no conn_variation_id, so they are deleted automatically
                    #we must call product_template_rebind (somewhere after posting)
                    if bindT:
                        #use it to post new item
                        res = bindT.product_template_post( meli=meli )
                        _logger.info("res bindT.product_template_post:"+str(res))
                        if res and 'name' in res:
                            return res
                else:
                    #post NEW PUB for each variant (new bind template also)
                    for variant in productT.product_variant_ids:
                        #meli_id = (variant.meli_id) or None
                        if variant.meli_id and not new_pub:
                            meli_id = variant.meli_id
                        else:
                            meli_id = None
                        bindT = productT.mercadolibre_bind_to( account=account, meli_id=meli_id, meli=meli, bind_variant=variant )
                        if bindT:
                            res = bindT.product_template_post( meli=meli, product_variant=variant )
                            if res and 'name' in res:
                                return res

            #UPDATE OLD
            else:
                #re post all bindings...
                _logger.info("[PRODUCT.TEMPLATE] >> product_template_post > repost all bindings: " +str(productT.mercadolibre_bindings.mapped('conn_id')) )
                for bindT in productT.mercadolibre_bindings:
                    meli_id_match = meli_id and ( meli_id==bindT.conn_id )
                    if not meli_id or meli_id_match:
                        res = bindT.product_template_post( meli=meli )
                        _logger.info("bindT.product_template_post res: "+str(res))
                        if res and 'name' in res:
                            return res

        return res

    def action_meli_pause(self):
        for product in self:
            for bind in product.mercadolibre_bindings:
                bind.product_meli_status_pause()
                #if (variant.meli_pub):
                #    variant.product_meli_status_pause()
            #for variant in product.product_variant_ids:
                #if (variant.meli_pub):
                #    variant.product_meli_status_pause()
        return {}

    def action_meli_activate(self):
        for product in self:
            for bind in product.mercadolibre_bindings:
                bind.product_meli_status_active()
            #for variant in product.product_variant_ids:
                #if (variant.meli_pub):
                #    variant.product_meli_status_active()
        return {}

    def action_meli_close(self):
        for product in self:
            for bind in product.mercadolibre_bindings:
                bind.product_meli_status_close()
            #for variant in product.product_variant_ids:
                #if (variant.meli_pub):
                #    variant.product_meli_status_close()
        return {}

    def action_meli_delete(self):
        for product in self:
            for bind in product.mercadolibre_bindings:
                bind.product_meli_delete()
            #for variant in product.product_variant_ids:
                #if (variant.meli_pub):
                #    variant.product_meli_delete()
        return {}

    def product_template_post_stock( self, context=None, meli=None, account=None ):
        _logger.info("producte.template: product_template_post_stock")
        res = []
        for productT in self:
            for bindT in productT.mercadolibre_bindings:
                condition = not account
                condition = condition or (account and bindT.connection_account and account.id == bindT.connection_account.id )
                if condition:
                    r = bindT.product_template_post_stock(meli=meli,account=account)
                    res.append(r)
        return res

    def product_template_post_price( self, context=None, meli=None, account=None ):
        _logger.info("producte.template: product_template_post_price")
        res = []
        for productT in self:
            for bindT in productT.mercadolibre_bindings:
                condition = not account
                condition = condition or (account and bindT.connection_account and account.id == bindT.connection_account.id )
                if condition:
                    r = bindT.product_template_post_price(meli=meli,account=account)
                    res.append(r)
        return res


class product_product(models.Model):

    _inherit = "product.product"

    mercadolibre_bindings = fields.Many2many( "mercadolibre.product", string="MercadoLibre Connection Bindings", copy=False )

    def _meli_price_converted( self, meli_price=None, config=None ):
        company = (config and 'company_id' in config._fields and config.company_id) or self.env.user.company_id
        config = config or company
        _logger.info("_meli_set_product_price: config: "+str(config and config.name))
        ml_price_converted = meli_price
        product = self
        product_template = self.product_tmpl_id
        tax_excluded = ml_tax_excluded(self, config=config)

        if ( tax_excluded and product_template.taxes_id ):
            _logger.info("Adjust taxes")
            txfixed = 0
            txpercent = 0
            #_logger.info("Adjust taxes")
            for txid in product_template.taxes_id:
                if (txid.type_tax_use=="sale" and not txid.price_include):
                    if (txid.amount_type=="percent"):
                        txpercent = txpercent + txid.amount
                    if (txid.amount_type=="fixed"):
                        txfixed = txfixed + txid.amount
            if (txfixed>0 or txpercent>0):
                #_logger.info("Tx Total:"+str(txtotal)+" to Price:"+str(ml_price_converted))
                ml_price_converted = txfixed + ml_price_converted / (1.0 + txpercent*0.01)
                _logger.info("Price adjusted with taxes:"+str(ml_price_converted))

        return ml_price_converted

    def ocapi_price(self, account):
        return self.lst_price

    def _ocapi_virtual_available(self, account):

        product_id = self
        qty_available = product_id.virtual_available
        #loc_id = self._ocapi_get_location_id()

        #quant_obj = self.env['stock.quant']

        #qty_available = quant_obj._get_available_quantity(product_id, loc_id)

        return qty_available

    def ocapi_stock(self, account=None):
        stocks = []
        #ss = variant._product_available()
        sq = self.env["stock.quant"].search([('product_id','=',self.id)])
        if (sq):
            _logger.info( sq )
            #_logger.info( sq.name )
            for s in sq:
                if ( s.location_id.usage == "internal" ):
                    _logger.info( s )
                    sjson = {
                        "warehouseId": s.location_id.id,
                        "warehouse": s.location_id.display_name,
                        "quantity": s.quantity,
                        "reserved": s.reserved_quantity,
                        "available": s.quantity - s.reserved_quantity
                    }
                    stocks.append(sjson)
        return stocks

    def mercadolibre_image_url_principal(self):
        code = self.default_code or self.barcode
        return "/ocapi/mercadolibre/img/%s/%s/%s" % (str(self.id), str(code), str("default") )

    def mercadolibre_image_id_principal(self):
        return "%s" % ( str(self.id) )

    def mercadolibre_image_url(self, image):
        code = self.default_code or self.barcode
        return "/ocapi/mercadolibre/img/%s/%s/%s" % (str(self.id), str(code), str(image.id) )

    def mercadolibre_image_id(self, image):
        return "%s" % ( str(image.id) )

    def mercadolibre_bind_variation_id( self, account=None, meli_id=None, meli=None, rjson=None ):

        #associate using SKU
        product = self

        _logger.info("associate using SKU or combination")

        meli_id_variation = False

        if not rjson:
            return meli_id_variation

        if ("variations" in rjson and len(rjson["variations"]) ):

            for var in rjson["variations"]:

                sku = ("seller_sku" in var and var["seller_sku"]) or ("seller_custom_field" in var and var["seller_custom_field"]) or None
                bcode = ("barcode" in var and var["barcode"]) or None

                seller_sku = None

                if sku and product.default_code:
                    #TODO: cap unsensitive comparison?
                    _logger.info("mercadolibre_bind_variation_id >> check sku and default_code: "+str(sku)+" vs." + str(product.default_code) )
                    if product.default_code == sku:
                        _logger.info("mercadolibre_bind_variation_id >> meli_id_variation match: same SKU: " + product.name + " << " + str(sku))
                        meli_id_variation = var["id"]
                        seller_sku = sku
                        barcode = bcode

                if not sku or not product.default_code:
                    #check if combination is related to base product binded variant
                    _logger.info("mercadolibre_bind_variation_id >> check combination: "+str(product._combination())+" vs." + str(var) )
                    if (product._is_product_combination(var)):
                        meli_id_variation = var["id"]
                        _logger.info("mercadolibre_bind_variation_id >> meli_id_variation match: "+str(meli_id_variation)+" >> var: "+str(var) )

            if not meli_id_variation:
                _logger.error("mercadolibre_bind_variation_id >> meli_id_variation NOT match: "+str(meli_id_variation) )

        else: #no variations
            sku = ("seller_sku" in rjson and rjson["seller_sku"]) or ("seller_custom_field" in rjson and rjson["seller_custom_field"])
            bcode = ("barcode" in rjson and rjson["barcode"])

            seller_sku = None

            if sku and product.default_code == sku:
                seller_sku = sku
                barcode = bcode
                meli_id_variation = None

            if not seller_sku:
                #abort binding (using Only SKU binding)
                _logger.error(_("mercadolibre_bind_to >> Aborting binding product (using Only SKU: NO SKU) %s to %s, id: %s, var id: %s, sku: %s") % (product.display_name, account.name, str(meli_id), str(meli_id_variation),str(seller_sku)))
                seller_sku = "__undefined__"
                meli_id_variation = "__undefined__"

        return meli_id_variation

    def mercadolibre_bind_to( self, account, binding_product_tmpl_id=False, meli_id=None, meli_id_variation=None, meli=None, rjson=None, bind_only=False ):
        pv_bind = None
        _logger.info( "mercadolibre_bind_to >> product bind_only: " + str(bind_only)+" meli_id: "+str(meli_id)+" meli_id_variation: "+str(meli_id_variation)+" context:"+str(self.env.context) )
        for product in self:

            for bind in product.mercadolibre_bindings:
                if (account.id in bind.connection_account.ids):
                    #account ok, now check if conn_id/meli_id is ok.
                    if ( bind.conn_id == meli_id ):
                        _logger.info("No need to add")
                        continue;

            if not meli:
                meli = self.env['meli.util'].get_new_instance( account.company_id, account)

            if rjson or meli_id:
                rjson = rjson or account.fetch_meli_product( meli_id = meli_id, meli=meli )

            meli_title = (rjson and "title" in rjson and rjson["title"].encode("utf-8")) or product.name
            seller_sku = False
            barcode = False

            #TODO: check if id variation correspond really to this default_code/sku or attribute combination
            product_not_imported = (product and not product.meli_id and meli_id and (1==1))
            product_imported_not_matching_binding = (product and product.meli_id and meli_id and product.meli_id!=meli_id)
            bind_only = bind_only or ( product_not_imported ) or (product_imported_not_matching_binding)
            _logger.info("bind_only: "+str(bind_only))
            if (meli_id_variation==None and bind_only==True):
                meli_id_variation = product.mercadolibre_bind_variation_id( account=account, meli_id=meli_id, meli=meli, rjson=rjson )


            meli_id_variation = meli_id_variation or (bind_only==False and meli_id and product.meli_id==meli_id and product.meli_id_variation)
            seller_sku = seller_sku or (bind_only==False and product.default_code) or ''
            barcode = barcode or (bind_only==False and product.barcode) or ''
            _logger.info(_("mercadolibre_bind_to >> Adding/Update product %s to %s, id: %s, var id: %s, sku: %s") % (product.display_name, account.name, str(meli_id), str(meli_id_variation),str(seller_sku)))

            try:

                prod_binding = {
                    "connection_account": account.id,
                    "product_tmpl_id": product.product_tmpl_id.id,
                    "product_id": product.id,
                    "name": meli_title,
                    "meli_title": meli_title,
                    "description": product.description_sale, #TODO: same as seller_sku and barcode
                    "sku": seller_sku,
                    "barcode": barcode,
                    "conn_id": meli_id,
                    "conn_variation_id": meli_id_variation,
                    #TODO deprecated meli_id and meli_id_variation
                    "meli_id": meli_id,
                    "meli_id_variation": meli_id_variation,
                    #"price": product.ocapi_price(account),
                    #"stock": product.ocapi_stock(account),
                }

                #Binding Product Template (parent) if missing
                if binding_product_tmpl_id:
                    prod_binding["binding_product_tmpl_id"] = binding_product_tmpl_id.id
                else:
                    pt_bind = self.env["mercadolibre.product_template"].search([("conn_id","=",meli_id),
                                                                                ("product_tmpl_id","=",product.product_tmpl_id.id),
                                                                                ("connection_account","=",account.id)])
                    if pt_bind and len(pt_bind):
                        prod_binding["binding_product_tmpl_id"] = pt_bind[0].id
                    else:
                        _logger.info( "Binding template: " + str(product.product_tmpl_id) )
                        pt_bind = product.product_tmpl_id.mercadolibre_bind_to( account, meli_id=meli_id, bind_variants=False, meli=meli, rjson=rjson, bind_only=bind_only )
                        if pt_bind and len(pt_bind):
                            prod_binding["binding_product_tmpl_id"] = pt_bind[0].id

                #Binding Variant finally
                #_logger.info(prod_binding)

                pv_bind = self.env["mercadolibre.product"].search([ ("conn_id","=",meli_id),
                                                                    ("conn_variation_id","=",meli_id_variation),
                                                                    ("product_id","=",product.id),
                                                                    ("product_tmpl_id","=",product.product_tmpl_id.id),
                                                                    ("connection_account","=",account.id)])

                if pv_bind: #unlink last ones
                    _logger.info( "Found [complete] var binding: " + str(pv_bind) )
                    if len(pv_bind)>1:
                        pvba = None
                        for pvb in pv_bind:
                            if pvba:
                                _logger.info("Unlinking:"+str(pvba))
                                pvba.unlink()
                            pvba = pvb

                if not pv_bind: #then search first for any variant binding with same conn_variation_id == meli_id_variation
                    pv_bind = self.env["mercadolibre.product"].search([ ("conn_id","=",meli_id),
                                                                        ("conn_variation_id","=",meli_id_variation),
                                                                        #search not using product id: ("product_id","=",product.id),
                                                                        ("product_tmpl_id","=",product.product_tmpl_id.id),
                                                                        ("connection_account","=",account.id)])
                    if pv_bind:
                        #unlink last ones
                        _logger.info( "Found [conn_variation_id] var binding: " + str(pv_bind) )
                        if len(pv_bind)>1:
                            pvba = None
                            for pvb in pv_bind:
                                if pvba:
                                    _logger.info("Unlinking:"+str(pvba))
                                    pvba.unlink()
                                pvba = pvb

                if not pv_bind: #then search first for any variant binding binded to this product  - always from this publication
                    pv_bind = self.env["mercadolibre.product"].search([ ("conn_id","=",meli_id),
                                                                    #("conn_variation_id","=",meli_id_variation or product.meli_id_variation),
                                                                    ("product_id","=",product.id),
                                                                    ("product_tmpl_id","=",product.product_tmpl_id.id),
                                                                    ("connection_account","=",account.id)])

                    if pv_bind:
                        #unlink last ones
                        _logger.info( "Found [product_id] var binding: " + str(pv_bind) )
                        if len(pv_bind)>1:
                            pvba = None
                            for pvb in pv_bind:
                                if pvba:
                                    pvba.unlink()
                                pvba = pvb




                if pv_bind and len(pv_bind):
                    #_logger.info(pv_bind)
                    pv_bind = pv_bind[0]
                    _logger.info("rewrite variant binding: " + str(prod_binding))
                    pv_bind.write(prod_binding)
                else:
                    #really need to create it
                    _logger.info("creating variant binding: " + str(prod_binding))
                    pv_bind = self.env["mercadolibre.product"].create([prod_binding])

                if pv_bind:

                    pv_bind.copy_from_rjson( rjson=rjson, meli=meli )

                    product.mercadolibre_bindings = [(4, pv_bind.id)]

                    if (meli_id_variation):
                        #drop all UNASSIGNED bindings for this meli_id_variation
                        un_pv_bind = self.env["mercadolibre.product"].search([ ("conn_id","=",meli_id),
                                                                            ("conn_variation_id","=",meli_id_variation),
                                                                            ("product_id","=",False),
                                                                            ("product_tmpl_id","=",product.product_tmpl_id.id),
                                                                            ("connection_account","=",account.id)])
                        if un_pv_bind:
                            pvba = None
                            for pvb in un_pv_bind:
                                pvba = pvb
                                if pvba:
                                    _logger.info("Unlink UNASSIGNED")
                                    pvba.unlink()

                    if (not meli_id_variation):
                        #drop all UNASSIGNED bindings
                        un_pv_bind = self.env["mercadolibre.product"].search([ ("conn_id","=",meli_id),
                                                                            ("conn_variation_id","=",False),
                                                                            ("product_id","=",False),
                                                                            ("product_tmpl_id","=",product.product_tmpl_id.id),
                                                                            ("connection_account","=",account.id)])
                        if un_pv_bind:
                            pvba = None
                            for pvb in un_pv_bind:
                                pvba = pvb
                                if pvba:
                                    _logger.info("Unlink UNASSIGNED")
                                    pvba.unlink()

            except Exception as e:
                _logger.error(e, exc_info=True)

        return pv_bind

    def mercadolibre_unbind_from( self, account, binding_product_tmpl_id=False, meli_id=None, meli_id_variation=None):
        pv_bind = None

        for product in self:

            for bind in product.mercadolibre_bindings:
                if not (account.id in bind.connection_account.ids):
                    _logger.info("No need to remove")
                    continue;

            _logger.info(_("Removing product %s from %s") % (product.display_name, account.name))
            try:
                meli_id_filter = []
                meli_id = meli_id or (binding_product_tmpl_id and binding_product_tmpl_id.conn_id)
                if meli_id:
                    meli_id_filter = [('conn_id','=',meli_id)]
                if meli_id and meli_id_variation:
                    meli_id_filter = [('conn_id','=',meli_id),('conn_variation_id','=',meli_id_variation)]
                pv_binds = self.env["mercadolibre.product"].search([("product_id","=",product.id),
                                                                    ("connection_account","=",account.id)]
                                                                    + meli_id_filter )

                for pv_bind in pv_binds:

                    if pv_bind:
                        product.mercadolibre_bindings = [(3, pv_bind.id)]
                        pv_bind.unlink()

            except Exception as e:
                _logger.error(e, exc_info=True)

        return pv_bind

    def is_variant_in_combination( self, ml_var_comb_default_code, var_default_code ):
        splits = ml_var_comb_default_code.split(";")
        is_in = True
        for att in splits:
            att_closed = att+";"
            if not att_closed in var_default_code:
                is_in = False
                break;
        return is_in

    def product_meli_get_product( self, meli_id=None, account=None, meli=None, rjson=None ):
        product = self
        meli_id = meli_id or product.meli_id
        product.meli_id = meli_id

        _logger.info("meli_oerp_multiple >> product_meli_get_product >> meli_id: "+str(meli_id)+" default_code: "+str(product.default_code))
        if not account:
            return { "error": "product_meli_get_product: no account" }

        company = (account and account.company_id) or self.env.user.company_id
        config = account.configuration
        product_obj = self.env['product.product']
        uomobj = self.env[uom_model]
        #pdb.set_trace()

        product_template_obj = self.env['product.template']
        product_template = product_template_obj.browse(product.product_tmpl_id.id)

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company, account)

        try:
            #response = meli.get("/items/"+product.meli_id, {'access_token':meli.access_token})
            #_logger.info(response)
            rjson = rjson or account.fetch_meli_product( meli_id=product.meli_id )
            #_logger.info(rjson)
        except IOError as e:
            _logger.error( "I/O error({0}): {1}".format(e.errno, e.strerror) )
            return { "error": "product_meli_get_product I/O error({0}): {1}".format(e.errno, e.strerror) }
        except:
            _logger.error( "Rare error" )
            return { "error": "Rare error" }

        des = ''
        desplain = ''
        vid = ''
        if 'error' in rjson:
            return { "error": rjson["error"] }

        #TODO: traer la descripcion: con
        #https://api.mercadolibre.com/items/{ITEM_ID}/description?access_token=$ACCESS_TOKEN
        if rjson and 'descriptions' in rjson:
            response2 = meli.get("/items/"+str(meli_id)+"/description", {'access_token':meli.access_token})
            rjson2 = response2.json()
            if 'text' in rjson2:
               des = rjson2['text']
            if 'plain_text' in rjson2:
               desplain = rjson2['plain_text']
            if (len(des)>0):
                desplain = des

        #TODO: verificar q es un video
        if 'video_id' in rjson and rjson['video_id']:
            vid = rjson['video_id']

        #TODO: traer las imagenes
        #TODO:
        pictures = rjson['pictures']
        if pictures and len(pictures):
            #remove all meli images not in pictures:
            product._meli_remove_images_unsync( product_template, pictures )
            product._meli_set_images(product_template, pictures)

        #categories
        product._meli_set_category( product_template, rjson['category_id'] )

        #prices
        force_price_for_variant = True

        # if 2 or more variations, its a variant publication, one price for all else one for each product variant as they are independent
        if "variations" in rjson and len(rjson["variations"])>1:
            force_price_for_variant = False

        try:
            if (float(rjson['price'])>=0.0):
                product._meli_set_product_price( product_template, rjson['price'], force_variant=force_price_for_variant, config=config )
        except Exception as e:
            _logger.error(e, exc_info=True)
            rjson['price'] = 0.0

        imagen_id = ''
        meli_dim_str = ''
        if ('dimensions' in rjson):
            if (rjson['dimensions']):
                meli_dim_str = rjson['dimensions']

        if ('pictures' in rjson):
            if (len(rjson['pictures'])>0):
                imagen_id = rjson['pictures'][0]['id']

        try:
            if (float(rjson['price'])>=0.0):
                product._meli_set_product_price( product_template, rjson['price'], config=config )
        except:
            rjson['price'] = 0.0

        try:
            rjson['warranty'] = rjson['warranty']
        except:
            pass;

        meli_fields = {
            'name': rjson['title'].encode("utf-8"),
            #'default_code': rjson['id'],
            'meli_imagen_id': imagen_id,
            #'meli_post_required': True,
            'meli_id': rjson['id'],
            'meli_permalink': rjson['permalink'],
            'meli_title': rjson['title'].encode("utf-8"),
            'meli_description': desplain,
            'meli_listing_type': rjson['listing_type_id'],
            'meli_buying_mode':rjson['buying_mode'],
            'meli_price': str(rjson['price']),
            'meli_price_fixed': True,
            'meli_currency': rjson['currency_id'],
            'meli_condition': rjson['condition'],
            'meli_available_quantity': rjson['available_quantity'],
            'meli_warranty': rjson['warranty'],
            'meli_imagen_link': rjson['thumbnail'],
            'meli_video': str(vid),
            'meli_dimensions': meli_dim_str,
        }

        tmpl_fields = {
          'name': meli_fields["name"],
          'description_sale': desplain,
          #'name': str(rjson['id']),
          #'lst_price': ml_price_convert,
          'meli_title': meli_fields["meli_title"],
          'meli_description': meli_fields["meli_description"],
          #'meli_category': meli_fields["meli_category"],
          'meli_listing_type': meli_fields["meli_listing_type"],
          'meli_buying_mode': meli_fields["meli_buying_mode"],
          'meli_price': meli_fields["meli_price"],
          'meli_currency': meli_fields["meli_currency"],
          'meli_condition': meli_fields["meli_condition"],
          'meli_warranty': meli_fields["meli_warranty"],
          'meli_dimensions': meli_fields["meli_dimensions"]
        }

        if (product.name and not config.mercadolibre_overwrite_variant):
            del meli_fields['name']
        if (product_template.name and not config.mercadolibre_overwrite_template):
            del tmpl_fields['name']
        if (product_template.description_sale and not config.mercadolibre_overwrite_template):
            del tmpl_fields['description_sale']

        if ("catalog_listing" in rjson):
            meli_fields["meli_catalog_listing"] = rjson["catalog_listing"]
            if (meli_fields["meli_catalog_listing"]==True):
                tmpl_fields["meli_catalog_listing"] = True

            if ("automatic_relist" in rjson):
                meli_fields["meli_catalog_automatic_relist"] = rjson["automatic_relist"]
                if (meli_fields["meli_catalog_listing"]==True):
                    tmpl_fields["meli_catalog_automatic_relist"] = True

            if ("catalog_product_id" in rjson):
                meli_fields["meli_catalog_product_id"] = rjson["catalog_product_id"]
                if (meli_fields["meli_catalog_listing"]==True):
                    tmpl_fields["meli_catalog_product_id"] = rjson["catalog_product_id"]

            if ("item_relations" in rjson):
                meli_fields["meli_catalog_item_relations"] = rjson["item_relations"]
                if (meli_fields["meli_catalog_listing"]==True):
                    tmpl_fields["meli_catalog_item_relations"] = rjson["item_relations"]

        product.write( meli_fields )
        product_template.write( tmpl_fields )

        if (rjson['available_quantity']>=0):
            if (product_template.type not in ['product']):
                try:
                    product_template.write( { 'type': 'product' } )
                except Exception as e:
                    _logger.info("Set type almacenable ('product') not possible:")
                    _logger.error(e, exc_info=True)
                    pass;
            #TODO: agregar parametro para esto: ml_auto_website_published_if_available  default true
            if (1==1 and rjson['available_quantity']>0):
                product_template.website_published = True

        #TODO: agregar parametro para esto: ml_auto_website_unpublished_if_not_available default false
        if (1==2 and rjson['available_quantity']==0):
            product_template.website_published = False

        posting_fields = {
            'posting_date': str(datetime.now()),
            'meli_id':rjson['id'],
            'product_id':product.id,
            'name': 'Post ('+str(product.meli_id)+'): ' + product.meli_title
        }

        posting = self.env['mercadolibre.posting'].search([('meli_id','=',rjson['id'])])
        posting_id = posting.id

        if not posting_id:
            posting = self.env['mercadolibre.posting'].create((posting_fields))
            posting_id = posting.id
            #if (posting):
            #    posting.posting_query_questions()
        else:
            posting.write({'product_id':product.id })
            #posting.posting_query_questions()

        b_search_nonfree_ship = False
        if ('shipping' in rjson):

            if "logistic_type" in rjson["shipping"]:
                product.meli_shipping_logistic_type = rjson["shipping"]["logistic_type"]

            att_shipping = {
                'name': 'Con envío',
                'create_variant': default_no_create_variant
            }
            if ('variations' in rjson):
                #_logger.info("has variations")
                pass
            else:
                rjson['variations'] = []

            if ('free_methods' in rjson['shipping']):
                att_shipping['value_name'] = 'Sí'
                #buscar referencia del template correspondiente
                b_search_nonfree_ship = True
            else:
                att_shipping['value_name'] = 'No'

            rjson['variations'].append({'attribute_combinations': [ att_shipping ]})

        #_logger.info(rjson['variations'])
        #COMPLETING ATTRIBUTES VARIATION INFORMATION FROM /items/[MLID]/variations/[VARID]...
        if ('variations' in rjson and 1==1):
            vindex = -1
            realmeliv = 0
            for variation in rjson['variations']:
                vindex = vindex+1
                #_logger.info(variation)
                #_logger.info(rjson['variations'][vindex])
                if 'id' in rjson['variations'][vindex]:
                    #_logger.info(vid)
                    realmeliv = realmeliv+1
                    vid = rjson['variations'][vindex]['id']
                    #resvar = meli.get("/items/"+str(product.meli_id)+"/variations/"+str(vid), {'access_token':meli.access_token})
                    #vjson = resvar.json()
                    vjson = variation
                    #if ( "error" in vjson ):
                    #    continue;
                    if ("attributes" in vjson):
                        rjson['variations'][vindex]["attributes"] = vjson["attributes"]
                        for att in vjson["attributes"]:
                            if ("id" in att and att["id"] == "SELLER_SKU"):
                                rjson['variations'][vindex]["seller_sku"] = att["value_name"]
            #_logger.info(rjson['variations'])

            if ( realmeliv>0 and 1==1 ):
                #associate var ids for every variant
                product_template.meli_pub_as_variant = True
                if (not product_template.meli_pub_principal_variant
                    or not product_template.meli_pub_principal_variant.id == product.id):
                    for variant in product_template.product_variant_ids:
                        if not product_template.meli_pub_principal_variant:
                            product_template.meli_pub_principal_variant = variant
                        for variation in rjson['variations']:
                            if ("seller_sku" in variation and variant.default_code == variation["seller_sku"]):
                                variant.meli_id_variation = variation["id"]
                                variant.meli_pub = True
                                variant.meli_id = product.meli_id
                                variant.meli_available_quantity = variation["available_quantity"]

        published_att_variants = False
        if (config.mercadolibre_update_existings_variants and 'variations' in rjson):
            published_att_variants = self._get_variations( rjson['variations'])

        #_logger.info("product_uom_id")
        product_uom_id = uomobj.search([('name','=','Unidad(es)')])
        if (product_uom_id.id==False):
            product_uom_id = 1
        else:
            product_uom_id = product_uom_id.id

        _product_id = product.id
        _product_name = product.name
        _product_meli_id = product.meli_id

        #this write pull the trigger for create_variant_ids()...
        #_logger.info("rewrite to create variants")
        if (config.mercadolibre_update_existings_variants):
            product_template.write({ 'attribute_line_ids': product_template.attribute_line_ids  })

        _logger.info("published_att_variants: "+str(published_att_variants))
        if (published_att_variants):
            product_template.meli_pub_as_variant = True

            #_logger.info("Auto check product.template meli attributes to publish")
            for line in  product_template.attribute_line_ids:
                if (line.id not in product_template.meli_pub_variant_attributes.ids):
                    if (line.attribute_id.create_variant=="always"):
                        product_template.meli_pub_variant_attributes = [(4,line.id)]

            _logger.info("check variants")
            for variant in product_template.product_variant_ids:
                _logger.info("Created variant:")
                _logger.info(variant)
                variant.meli_pub = product_template.meli_pub
                variant.meli_id = rjson['id']
                #variant.default_code = rjson['id']
                #variant.name = rjson['title'].encode("utf-8")
                has_sku = False

                _v_default_code = ""
                for att in att_value_ids(variant):
                    _v_default_code = _v_default_code + att.attribute_id.name+':'+att.name+';'
                _logger.info("_v_default_code: " + _v_default_code)
                for variation in rjson['variations']:
                    #_logger.info(variation)
                    _logger.info("variation[default_code]: " + variation["default_code"])
                    if ( len(variation["default_code"]) and variant.is_variant_in_combination( variation["default_code"], _v_default_code ) ):
                        if ("seller_custom_field" in variation or "seller_sku" in variation):
                            _logger.info("has_sku")
                            #_logger.info(variation["seller_custom_field"])
                            try:
                                variant.default_code = ("seller_sku" in variation and variation["seller_sku"]) or variation["seller_custom_field"]
                                bcode = ("barcode" in variation and variation["barcode"]) or ''
                                #try:
                                #    variant.barcode = bcode
                                #except:
                                #    _logger.error("Duplicate variant.barcode:"+str(bcode))
                                #    pass;
                                if (len(rjson['variations'])==1):
                                    variant.product_tmpl_id.default_code = variant.default_code
                                    try:
                                        variant.product_tmpl_id.barcode = variant.barcode
                                    except:
                                        _logger.error("Duplicate product_tmpl_id.barcode: "+str(bcode))
                                        pass;
                            except:
                                pass;
                            variant.meli_id_variation = variation["id"]
                            has_sku = True
                        else:
                            variant.default_code = variant.meli_id+'-'+_v_default_code
                        variant.meli_available_quantity = variation["available_quantity"]

                if (has_sku):
                    variant.set_bom()

                #_logger.info('meli_pub_principal_variant')
                #_logger.info(product_template.meli_pub_principal_variant.id)
                if (product_template.meli_pub_principal_variant.id is False):
                    #_logger.info("meli_pub_principal_variant set!")
                    product_template.meli_pub_principal_variant = variant
                    product = variant

                if (_product_id==variant.id):
                    product = variant
        else:
            #NO TIENE variantes pero tiene SKU
            seller_sku = None
            if not seller_sku and "attributes" in rjson:
                for att in rjson['attributes']:
                    if att["id"] == "SELLER_SKU":
                        seller_sku = att["value_name"]
                        break;

            if (not seller_sku and "seller_sku" in rjson):
                seller_sku = rjson["seller_sku"]

            if (not seller_sku and "seller_custom_field" in rjson):
                seller_sku = rjson["seller_custom_field"]

            if seller_sku:
                product.default_code = seller_sku
                product.set_bom()
            bcode = ("barcode" in rjson and rjson["barcode"]) or ''
            try:
                #product.barcode = bcode
                product_tmpl_id.barcode = bcode
            except:
                _logger.error("Duplicate barcode: "+str(bcode))

        if (config.mercadolibre_update_local_stock):
            product_template.type = 'product'

            if (len(product_template.product_variant_ids)):
                for variant in product_template.product_variant_ids:

                    _product_id = variant.id
                    _product_name = variant.name
                    _product_meli_id = variant.meli_id

                    if (variant.meli_available_quantity != variant.virtual_available):
                        variant.product_update_stock(stock=variant.meli_available_quantity, meli=meli, config=config)
            else:
                product.product_update_stock(stock=product.meli_available_quantity, meli=meli, config=config )

        #assign envio/sin envio
        #si es (Con envio: Sí): asigna el meli_default_stock_product al producto sin envio (Con evio: No)
        if (b_search_nonfree_ship and 1==2):
            ptemp_nfree = False
            ptpl_same_name = self.env['product.template'].search([('name','=',product_template.name),('id','!=',product_template.id)])
            #_logger.info("ptpl_same_name:"+product_template.name)
            #_logger.info(ptpl_same_name)
            if len(ptpl_same_name):
                for ptemp in ptpl_same_name:
                    #check if sin envio
                    #_logger.info(ptemp.name)
                    for line in ptemp.attribute_line_ids:
                        #_logger.info(line.attribute_id.name)
                        #_logger.info(line.value_ids)
                        es_con_envio = False
                        try:
                            line.attribute_id.name.index('Con env')
                            es_con_envio = True
                        except ValueError:
                            pass
                            #_logger.info("not con envio")
                        if (es_con_envio==True):
                            for att in line.value_ids:
                                #_logger.info(att.name)
                                if (att.name=='No'):
                                    #_logger.info("Founded")
                                    if (ptemp.meli_pub_principal_variant.id):
                                        #_logger.info("has meli_pub_principal_variant!")
                                        ptemp_nfree = ptemp.meli_pub_principal_variant
                                        if (ptemp_nfree.meli_default_stock_product):
                                            #_logger.info("has meli_default_stock_product!!!")
                                            ptemp_nfree = ptemp_nfree.meli_default_stock_product
                                    else:
                                        if (ptemp.product_variant_ids):
                                            if (len(ptemp.product_variant_ids)):
                                                ptemp_nfree = ptemp.product_variant_ids[0]

            if (ptemp_nfree):
                #_logger.info("Founded ptemp_nfree, assign to all variants")
                for variant in product_template.product_variant_ids:
                    variant.meli_default_stock_product = ptemp_nfree

        if (config.mercadolibre_update_existings_variants and 'attributes' in rjson):
            self._get_non_variant_attributes(rjson['attributes'])

        return {}

    def product_update_stock(self, stock=False, meli_id=False, meli=False, config=None):
        product = self
        uomobj = self.env[uom_model]
        _stock = product.virtual_available
        meli_id = meli_id or product.meli_id

        try:
            if (stock!=False):
                _stock = stock
                if (_stock<0):
                    _stock = 0

            if (product.default_code):
                product.set_bom()

            if (product.meli_default_stock_product and meli_id!=product.meli_id):
                _stock = product.meli_default_stock_product._meli_available_quantity(meli=meli,config=config)
                if (_stock<0):
                    _stock = 0

            if (1==1 and _stock>=0 and product._meli_available_quantity( meli_id=meli_id, meli=meli, config=config )!=_stock):
                _logger.info("Updating stock for variant." + str(_stock) )
                #wh = self.env['stock.location'].search([('usage','=','internal')]).id
                #wh = product._meli_get_location_id(meli_id=product.id,meli=meli,config=config)
                wh = product._meli_get_location_id( meli_id=meli_id, meli=meli, config=config )
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

    #call with product_tmpl or bind template
    def _product_post_set_basic_configuration( self, product_tmpl=None, meli=None, config=None ):
        #check from company's default
        _logger.info("_product_post_set_basic_configuration: setting template configuration for this configuration.")
        product_tmpl.meli_listing_type = product_tmpl.meli_listing_type or config.mercadolibre_listing_type
        product_tmpl.meli_currency = product_tmpl.meli_currency or config.mercadolibre_currency
        product_tmpl.meli_condition = product_tmpl.meli_condition or config.mercadolibre_condition
        product_tmpl.meli_warranty = product_tmpl.meli_warranty or config.mercadolibre_warranty
        product_tmpl.meli_title = product_tmpl.meli_title or product_tmpl.name
        product_tmpl.meli_buying_mode = product_tmpl.meli_buying_mode or config.mercadolibre_buying_mode

        #Si la descripcion de template esta vacia la asigna del description_sale
        force_template_description = ( config.mercadolibre_product_template_override_variant
                                        and config.mercadolibre_product_template_override_method
                                        and config.mercadolibre_product_template_override_method in ['default','description','title_and_description']
                                        )
        product_tmpl.meli_description = (force_template_description and product_tmpl.description_sale) or product_tmpl.meli_description or product_tmpl.description_sale
        return {}

    def _product_post_set_price( self, meli_price=None, meli_pricelist=None, source_tmpl=None, target=None, meli=None, config=None ):
        #asigna del template si no esta definido
        source_tmpl.meli_price = meli_price or source_tmpl.meli_price
        if target.meli_price==False or target.meli_price==0.0 or target.meli_price!=source_tmpl.meli_price:
            if source_tmpl.meli_price:
                _logger.info("Assign source_tmpl price:"+str(meli_price or source_tmpl.meli_price))
                target.meli_price = source_tmpl.meli_price

    def _product_post_set_title( self, meli_title=None, source_tmpl=None, target=None, meli=None, config=None ):
        product_tmpl = source_tmpl
        product = target
        if (
            ( product.meli_title==False or len(product.meli_title)==0 )
            or
            ( product_tmpl.meli_pub_variant_attributes
                and not product_tmpl.meli_pub_as_variant
                    and len(product_tmpl.meli_pub_variant_attributes) )
            ):
            # _logger.info( 'Assigning title: product.meli_title: %s name: %s' % (product.meli_title, product.name) )
            product.meli_title = product_tmpl.meli_title

            if len(product_tmpl.meli_pub_variant_attributes):
                values = ""
                for line in product_tmpl.meli_pub_variant_attributes:
                    for value in att_value_ids(product):
                        if (value.attribute_id.id==line.attribute_id.id):
                            values+= " "+value.name
                if (not product_tmpl.meli_pub_as_variant):
                    product.meli_title = string.replace(product.meli_title,product.name,product.name+" "+values)

        force_template_title = meli_title or ( config.mercadolibre_product_template_override_variant
                                 and config.mercadolibre_product_template_override_method
                                 and config.mercadolibre_product_template_override_method in ['title','title_and_description']
                                )

        product_tmpl.meli_title = meli_title or product_tmpl.meli_title
        product.meli_title = ( force_template_title and product_tmpl.meli_title ) or product.meli_title

        if ( product.meli_title and len(product.meli_title)>60 ):
            message="La longitud del título ("+str(len(product.meli_title))+") es superior a 60 caracteres."
            raise ValidationError(message)
            #return warningobj.info( title='MELI WARNING', message="La longitud del título ("+str(len(product.meli_title))+") es superior a 60 caracteres.", message_html=product.meli_title )

    def _product_post_set_category( self, product_tmpl=None, product=None, meli=None, config=None ):
        www_cats = False
        if 'product.public.category' in self.env:
            www_cats = self.env['product.public.category']

        if www_cats:
            if product.public_categ_ids:
                for cat_id in product.public_categ_ids:
                    #_logger.info(cat_id)
                    if (cat_id.mercadolibre_category):
                        #_logger.info(cat_id.mercadolibre_category)
                        product.meli_category = cat_id.mercadolibre_category
                        product_tmpl.meli_category = cat_id.mercadolibre_category

        if product_tmpl.meli_category and not product.meli_category:
            product.meli_category = product_tmpl.meli_category

    def _product_post_set_quantity( self, target=None, product=None, meli_id=None, meli=None, config=None ):

        target.meli_available_quantity = product._meli_available_quantity( meli_id=meli_id, meli=meli, config=config)

    def _product_post_set_template_configuration( self, product_tmpl=None, product=None, meli=None, config=None ):
        warningobj = self.env['meli.warning']
        _logger.info("_product_post_set_template_configuration: from " + str(product_tmpl)+" to:"+str(product))
        res = {}
        #product template > product variant > binding template > binding variant
        force_template_description = ( config.mercadolibre_product_template_override_variant
                                        and config.mercadolibre_product_template_override_method
                                        and config.mercadolibre_product_template_override_method in ['default','description','title_and_description']
                                        )
        product.meli_description = (force_template_description and product_tmpl.meli_description) or product.meli_description or product_tmpl.meli_description
        if not product.meli_description:
            res = warningobj.info(title='MELI WARNING', message="Debe completar el campo description en la plantilla de MercadoLibre o del producto (Descripción de Ventas)", message_html="<h3>Descripción faltante</h3>")

        product.meli_category = product.meli_category or product_tmpl.meli_category
        product.meli_listing_type = product.meli_listing_type or product_tmpl.meli_listing_type
        product.meli_buying_mode = product.meli_buying_mode or product_tmpl.meli_buying_mode

        product.meli_price = product.meli_price or product_tmpl.meli_price
        product.meli_currency = product.meli_currency or product_tmpl.meli_currency
        product.meli_condition = product.meli_condition or product_tmpl.meli_condition
        product.meli_warranty = product.meli_warranty or product_tmpl.meli_warranty

        #TODO: check
        product.meli_shipping_mode =  product.meli_shipping_mode or product_tmpl.meli_shipping_mode
        product.meli_shipping_method =  product.meli_shipping_method or product_tmpl.meli_shipping_method

        product.meli_brand = product.meli_brand or product_tmpl.meli_brand
        product.meli_model = product.meli_model or product_tmpl.meli_model
        product.meli_brand = product_tmpl.meli_brand
        product.meli_model = product_tmpl.meli_model
        return res

    def _product_post_set_attributes( self, product_tmpl=None, product=None, meli=None, config=None ):
        attributes = []
        variations_candidates = False
        att_line_ids = ("attribute_line_ids" in product_tmpl._fields and product_tmpl.attribute_line_ids)

        #binding template
        att_line_ids = att_line_ids or ("product_tmpl_id" in product_tmpl._fields and product_tmpl.product_tmpl_id.attribute_line_ids )

        if att_line_ids:
            _logger.info(" att_line_ids:"+str(att_line_ids))
            for at_line_id in att_line_ids:
                atname = at_line_id.attribute_id.name
                is_not_variant_attribute = at_line_id.attribute_id.create_variant!='always'
                is_not_meli_variant_attribute = at_line_id.attribute_id.meli_default_id_attribute and not at_line_id.attribute_id.meli_default_id_attribute.variation_attribute
                is_not_meli_variant_attribute = is_not_meli_variant_attribute or (at_line_id.attribute_id.meli_default_id_attribute and at_line_id.attribute_id.meli_default_id_attribute.hidden and at_line_id.attribute_id.meli_default_id_attribute.variation_attribute)
                is_meli_gtin = (at_line_id.attribute_id.meli_default_id_attribute and at_line_id.attribute_id.meli_default_id_attribute.att_id=="GTIN")
                #atributos, no variantes! solo con un valor...
                if (len(at_line_id.value_ids)==1 and (is_not_variant_attribute or is_not_meli_variant_attribute or is_meli_gtin) ):
                    atval = at_line_id.value_ids.name
                    _logger.info(atname+":"+atval)
                    if (atname=="MARCA" or atname=="BRAND"):
                        attribute = { "id": "BRAND", "value_name": atval }
                        attributes.append(attribute)
                    if (atname=="MODELO" or atname=="MODEL"):
                        attribute = { "id": "MODEL", "value_name": atval }
                        attributes.append(attribute)

                    if (at_line_id.attribute_id.meli_default_id_attribute.id):
                        attribute = {
                            "id": at_line_id.attribute_id.meli_default_id_attribute.att_id,
                            "value_name": atval
                        }
                        attributes.append(attribute)
                elif (len(at_line_id.value_ids)>1):
                    variations_candidates = True

        if product.meli_brand and len(product.meli_brand) > 0:
            attribute = { "id": "BRAND", "value_name": product.meli_brand }
            attributes.append(attribute)
            _logger.info(attributes)
            product.meli_attributes = str(attributes)

        if product.meli_model and len(product.meli_model) > 0:
            attribute = { "id": "MODEL", "value_name": product.meli_model }
            attributes.append(attribute)
            _logger.info(attributes)
            product.meli_attributes = str(attributes)

        if attributes:
            _logger.info(attributes)
            product.meli_attributes = str(attributes)

        if (not variations_candidates):
            if ( (("default_code" in product._fields and product.default_code)) and config.mercadolibre_post_default_code):
                #SKU as attribute is default now
                attribute = { "id": "SELLER_SKU", "value_name": product.default_code }
                attributes.append(attribute)
                product.meli_attributes = str(attributes)
            if ( (("sku" in product._fields and product.sku)) and config.mercadolibre_post_default_code):
                #SKU as attribute is default now
                attribute = { "id": "SELLER_SKU", "value_name": product.sku }
                attributes.append(attribute)
                product.meli_attributes = str(attributes)
            if ( (("barcode" in product._fields and product.barcode)) and config.mercadolibre_post_default_code):
                #SKU as attribute is default now
                attribute = { "id": "GTIN", "value_name": product.barcode }
                attributes.append(attribute)
                product.meli_attributes = str(attributes)

        return attributes

    def _product_post_set_images( self, product_tmpl=None, product=None, meli=None, config=None ):
        warningobj = self.env['meli.warning']
        #publicando multiples imagenes
        multi_images_ids = {}
        if (variant_image_ids(product) or template_image_ids(product)):
            multi_images_ids = product.product_meli_upload_multi_images(meli=meli,config=config)
            _logger.info(multi_images_ids)
            if 'status' in multi_images_ids:
                _logger.error(multi_images_ids)
                #return warningobj.info( title='MELI WARNING', message="Error publicando imagenes", message_html="Error: "+str(("error" in multi_images_ids and multi_images_ids["error"]) or "")+" Status:"+str(("status" in multi_images_ids and multi_images_ids["status"]) or "") )
                return warningobj.info( title='MELI WARNING', message="Error publicando imagenes", message_html="Error: "+str(multi_images_ids), context = { "rjson": multi_images_ids })

        return multi_images_ids

    def _product_post_set_body( self, product_tmpl=None, product=None, meli=None, config=None, attributes=None, meli_imagen_id=None, meli_multi_imagen_id=None, productjson=None ):

        body = {
            "title": product.meli_title or '',
            "category_id": product.meli_category.meli_category_id or '0',
            "listing_type_id": product.meli_listing_type or '0',
            "buying_mode": product.meli_buying_mode or '',
            "price": product.meli_price  or '0',
            "currency_id": product.meli_currency  or '0',
            "condition": product.meli_condition  or '',
            "available_quantity": product.meli_available_quantity  or '0',
            #"warranty": product.meli_warranty or '',
            "sale_terms": product._update_sale_terms( meli=meli, productjson=productjson ),
            #"pictures": [ { 'source': product.meli_imagen_logo} ] ,
            "video_id": product.meli_video  or '',
        }

        #TODO: upgrade > body = product._validate_category_settings( body )

        bodydescription = {
            "plain_text": product.meli_description or '',
        }

        #product.meli_shipping_mode and body.update({ "shipping_mode": product.meli_shipping_mode })
        #product.meli_shipping_method and body.update({ "shipping_method": product.meli_shipping_method })
        shipping = {
            "mode": "not_specified",
            #"local_pick_up": false,
            #"free_shipping": false,
            #"methods": [],
            #"dimensions": null,
            #"tags": [],
            #"logistic_type": "not_specified",
            #"store_pick_up": false
        }
        product.meli_shipping_mode and  shipping.update( { "mode": product.meli_shipping_mode })
        product.meli_shipping_method and  shipping.update( { "methods": [ { "id": product.meli_shipping_method } ] } )
        shipping and body.update({ "shipping": shipping })
        _logger.info("shipping mode:"+str(shipping))
        #store id
        if config.mercadolibre_official_store_id:
            body["official_store_id"] = config.mercadolibre_official_store_id

        if (product.meli_id or ("conn_id" in product._fields and product.conn_id)):
            body = {
                "title": product.meli_title or '',
                #"buying_mode": product.meli_buying_mode or '',
                "price": product.meli_price or '0',
                #"condition": product.meli_condition or '',
                "available_quantity": product.meli_available_quantity or '0',
                #"warranty": product.meli_warranty or '',
                "sale_terms": product._update_sale_terms( meli=meli, productjson=productjson ),

                "pictures": [],
                "video_id": product.meli_video or '',
            }
            if (productjson):
                if ("attributes" in productjson):
                    if (len(attributes)):
                        dicatts = {}
                        for att in attributes:
                            dicatts[att["id"]] = att
                        attributes_ml =  productjson["attributes"]
                        x = 0
                        for att in attributes_ml:
                            if (att["id"] in dicatts):
                                attributes_ml[x] = dicatts[att["id"]]
                            else:
                                attributes.append(att)
                            x = x + 1

                        body["attributes"] =  attributes
                    else:
                        attributes =  productjson["attributes"]
                        body["attributes"] =  attributes
        else:
            body["description"] = bodydescription

        if len(attributes):
            body["attributes"] =  attributes



        if meli_imagen_id:
            if 'pictures' in body.keys():
                body["pictures"] = [ { 'id': meli_imagen_id } ]
            else:
                body["pictures"] = [ { 'id': meli_imagen_id } ]

            if (meli_multi_imagen_id):
                if 'pictures' in body.keys():
                    body["pictures"]+= meli_multi_imagen_id
                else:
                    body["pictures"] = meli_multi_imagen_id

            if product.meli_imagen_logo:
                if 'pictures' in body.keys():
                    body["pictures"]+= [ { 'source': product.meli_imagen_logo} ]
                else:
                    body["pictures"] = [ { 'source': product.meli_imagen_logo} ]
        else:
            imagen_producto = ""

        #TODO: OBSOLETE check and set only if no variations
        #if (not variations_candidates):
        if ( ("default_code" in product._fields and product.default_code) and config.mercadolibre_post_default_code):
            body["seller_custom_field"] = product.default_code

        if ( (("sku" in product._fields and product.sku)) and config.mercadolibre_post_default_code):
            #SKU as attribute is default now
            body["seller_custom_field"] = product.sku


        if "meli_max_purchase_quantity" in product._fields and product.meli_max_purchase_quantity:
            body["sale_terms"].append({
                "id": "PURCHASE_MAX_QUANTITY",
                "value_name": str(product.meli_max_purchase_quantity)
            })

        if "meli_manufacturing_time" in product._fields and product.meli_manufacturing_time:
            body["sale_terms"].append({
                "id": "MANUFACTURING_TIME",
                "value_name": str(product.meli_manufacturing_time)
            })

        return body, bodydescription

    def product_meli_upload_image( self, bind_tpl=None, meli=False, config=False ):

        company = self.env.user.company_id
        config = config or company

        product_obj = self.env['product.product']
        product = self

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company)
            if meli.need_login():
                return meli.redirect_login()

        first_image_to_publish = get_first_image_to_publish( product )

        if first_image_to_publish==None or first_image_to_publish==False:
            return { 'status': 'error', 'message': 'no image to upload' }
        _logger.info("product_meli_upload_image: ")
        imagebin = base64.b64decode(first_image_to_publish)
        imageb64 = first_image_to_publish
        files = { 'file': ('image.jpg', imagebin, "image/jpeg"), }
        product_image = None
        try:
            hash = hashlib.blake2b()
            hash.update(imagebin)
            #product_image.meli_imagen_hash = hash.hexdigest()
            if (config.mercadolibre_do_not_use_first_image):
                product_image = variant_image_ids(product)[0]
                if (product_image):
                    product_image.meli_imagen_hash = hash.hexdigest()

        except:
            pass;
        _logger.info("product_meli_upload_image: "+str(len(files)) )
        response = meli.upload("/pictures", files, { 'access_token': meli.access_token } )

        rjson = response.json()
        if ("error" in rjson):
            #raise osv.except_osv( _('MELI WARNING'), _('No se pudo cargar la imagen en MELI! Error: %s , Mensaje: %s, Status: %s') % ( rjson["error"], rjson["message"],rjson["status"],))
            return rjson
            #return { 'status': 'error', 'message': 'not uploaded'}

        _logger.info( rjson )

        if ("id" in rjson):
            #guardar id
            if not bind_tpl:
                product.write( { "meli_imagen_id": rjson["id"], "meli_imagen_link": rjson["variations"][0]["url"] })
                if (product_image):
                    product_image.meli_imagen_id = rjson["id"]
                    product_image.meli_imagen_link = rjson["variations"][0]["secure_url"]
                    product_image.meli_imagen_size = rjson["variations"][0]["size"]
            #asociar imagen a producto
                if product.meli_id:
                    return rjson["id"]
                #response = meli.post("/items/"+product.meli_id+"/pictures", { 'id': rjson["id"] }, { 'access_token': meli.access_token } )
                else:
                    return { 'status': 'warning', 'message': 'uploaded but not assigned' }

        return { 'status': 'success', 'message': 'uploaded and assigned' }

    def _product_set_variations( self, product_tmpl=None, product=None, bind_tpl=None, meli=None, config=None, attributes=None, productjson=None, body=None, bodydescription=None ):
        warningobj = self.env['meli.warning']
        source = product_tmpl
        target = product
        meli_id = (bind_tpl and bind_tpl.conn_id) or product.meli_id
        #product_tmpl = "" in source._fields
        if (product_tmpl.meli_pub_as_variant):
            #es probablemente la variante principal
            if (product_tmpl.meli_pub_principal_variant and product_tmpl.meli_pub_principal_variant.id):
                #esta definida la variante principal, veamos si es esta
                if (product_tmpl.meli_pub_principal_variant.id == product.id):
                    #esta es la variante principal, si aun el producto no se publico
                    #preparamos las variantes

                    # product_json is Product Json from ML
                    if ( productjson and len(productjson["variations"]) ):
                        #ya hay variantes publicadas en ML
                        body_varias = {
                            "title": body["title"],
                            "pictures": body["pictures"],
                            "variations": []
                        }

                        #TODO: add pictures from real variant images
                        var_pics = []
                        if (len(body["pictures"])):
                            for pic in body["pictures"]:
                                var_pics.append(pic['id'])

                        _logger.info("Variations already posted, must update them only")
                        vars_updated = self.env["product.product"]
                        for ix in range(len(productjson["variations"]) ):
                            var_info = productjson["variations"][ix]
                            #_logger.info("Variation to update!!")
                            #_logger.info(var_info)
                            var_product = product

                            for pvar in product_tmpl.product_variant_ids:
                                if (pvar._is_product_combination(var_info)):
                                    var_product = pvar
                                    #upgrade variant stock
                                    var_product.meli_available_quantity = var_product._meli_available_quantity(meli=meli,config=config)
                                    vars_updated+=var_product
                            #TODO: add SKU
                            var_attributes = var_product._update_sku_attribute( attributes=("attributes" in var_info and var_info["attributes"]), set_sku=config.mercadolibre_post_default_code)
                            var = {
                                "id": str(var_info["id"]),
                                "price": (bind_tpl and bind_tpl.meli_price) or str(product_tmpl.meli_price),
                                "available_quantity": var_product.meli_available_quantity,
                                "picture_ids": var_pics,
                            }
                            var_attributes and var.update({"attributes": var_attributes })
                            body_varias["variations"].append(var)
                        #variations = product_tmpl._variations()
                        #varias["variations"] = variations
                        _all_variations = product_tmpl._variations(config=config)
                        _updated_ids = vars_updated.mapped('id')
                        _logger.info(_updated_ids)
                        _new_candidates = product_tmpl.product_variant_ids.filtered(lambda pv: pv.id not in _updated_ids)
                        _logger.info(_new_candidates)
                        if _all_variations:
                            for aix in range(len(_all_variations)):
                                var_info = _all_variations[aix]
                                for pvar in _new_candidates:
                                    if (pvar._is_product_combination(var_info)):
                                        var_attributes = pvar._update_sku_attribute( attributes=("attributes" in var_info and var_info["attributes"]), set_sku=config.mercadolibre_post_default_code )
                                        var_attributes and var_info.update({"attributes": var_attributes })

                                        #body_varias se actualiza
                                        body_varias["variations"].append(var_info)

                                        _logger.info("news:")
                                        _logger.info(var_info)

                        _logger.info("body_varias (N var):"+str(body_varias) )
                        responsevar = meli.put("/items/"+str(meli_id), body_varias, {'access_token':meli.access_token})
                        rjsonv = responsevar.json()
                        _logger.info(rjsonv)
                        if ("error" in rjsonv):
                            error_msg = 'MELI RESP.: <h6>Mensaje de error</h6><br/><h6>Mensaje</h6> %s<br/><h6>Status</h6> %s<br/><h6>Cause</h6> %s<br/><h7>Error completo:</h7><span>%s</span><br/>' % (rjsonv["message"], rjsonv["status"], rjsonv["cause"], rjsonv["error"])
                            _logger.error(error_msg)
                            if (rjsonv["error"]=="forbidden"):
                                url_login_meli = meli.auth_url()
                                return warningobj.info( title='MELI WARNING', message="Debe iniciar sesión en MELI con el usuario correcto.", message_html="<br><br>"+error_msg, context = { "rjson": rjsonv })
                            else:
                                return warningobj.info( title='MELI WARNING', message="Completar todos los campos y revise el mensaje siguiente.", message_html="<br><br>"+error_msg, context = { "rjson": rjsonv })


                        #verifica combinaciones in re-asigna id de variation
                        #if ("variations" in rjsonv):
                        #    for ix in range(len(rjsonv["variations"]) ):
                        #        _var = rjsonv["variations"][ix]
                        #        for pvar in product_tmpl.product_variant_ids:
                        #            if (pvar._is_product_combination(_var) and 'id' in _var):
                        #                pvar.meli_id = productjson["id"]
                        #                pvar.meli_id_variation = _var["id"]
                        #                pvar.meli_price = str(_var["price"])

                        #_logger.debug(responsevar.json())
                        #resdes = meli.put("/items/"+product.meli_id+"/description", bodydescription, {'access_token':meli.access_token})
                        #_logger.debug(resdes.json())
                        del body['price']
                        del body['available_quantity']
                        #resbody = meli.put("/items/"+product.meli_id, body, {'access_token':meli.access_token})
                        return body

                        #_logger.debug(resbody.json())
                         #responsevar = meli.put("/items/"+product.meli_id, {"initial_quantity": product.meli_available_quantity, "available_quantity": product.meli_available_quantity }, {'access_token':meli.access_token})
                         #_logger.debug(responsevar)
                         #_logger.debug(responsevar.json())

                    else:
                        #first variations post
                        variations = product_tmpl._variations(config=config)
                        _logger.info("Variations:")
                        _logger.info(variations)
                        if (variations):
                            if bind_tpl:
                                for var in variations:
                                    var["price"] = bind_tpl.meli_price
                            body["variations"] = variations
                else:
                    _logger.debug("Variant not able to post, variant principal.")
                    return {}
            else:
                _logger.debug("Variant principal not defined yet. Cannot post.")
                return {}
        else:
            #caso 1 sola combinacion, se trata especialmente
            if ( productjson and len(productjson["variations"])==1 ):
                body_varias = {
                    "title": body["title"],
                    "pictures": body["pictures"],
                    "variations": []
                }
                var_pics = []
                if (len(body["pictures"])):
                    for pic in body["pictures"]:
                        var_pics.append(pic['id'])
                _logger.info("Single variation already posted, must update it")

                #update variations structure for: "attributes" (SELLER_SKU, GTIN), "stock", "price", and "pictures"
                for ix in range(len(productjson["variations"]) ):
                    _logger.info("Variation to update!!")
                    _logger.info(productjson["variations"][ix])
                    var_info = productjson["variations"][ix]
                    var = {
                        "id": str(productjson["variations"][ix]["id"]),
                        "price": str(product_tmpl.meli_price),
                        "available_quantity": product.meli_available_quantity,
                        "picture_ids": var_pics
                    }
                    var_attributes = product._update_sku_attribute( attributes=("attributes" in var_info and var_info["attributes"]), set_sku=config.mercadolibre_post_default_code )
                    var_attributes and var.update({"attributes": var_attributes })
                    body_varias["variations"].append(var)

                    #WARNING: only for single variation
                    if not bind_tpl:
                        product.meli_id_variation = productjson["variations"][ix]["id"]
                    else:
                        bind_tpl.conn_variation_id = productjson["variations"][ix]["id"]
                        if bind_tpl.variant_bindings:
                            bind_tpl.variant_bindings[0].conn_id = productjson["id"]
                            bind_tpl.variant_bindings[0].conn_variation_id = productjson["variations"][ix]["id"]

                #variations = product_tmpl._variations()
                #varias["variations"] = variations

                _logger.info("body_varias (1 var):"+str(body_varias))
                responsevar = meli.put("/items/"+str(meli_id), body_varias, {'access_token':meli.access_token})
                _logger.info(responsevar.json())
                #_logger.debug(responsevar.json())
                #resdes = meli.put("/items/"+product.meli_id+"/description", bodydescription, {'access_token':meli.access_token})
                #_logger.debug(resdes.json())
                del body['price']
                del body['available_quantity']
                #resbody = meli.put("/items/"+product.meli_id, body, {'access_token':meli.access_token})
                #return {}
        return body

    ## special _product_post   that accept a binding variant as parameter to post...
    #
    # @param bind_tpl binded template; used when posting an alternative derived binded publication (not the base product)
    # @param bind  binded variant; specify the variant binding
    def _product_post( self, bind_tpl=None, bind=None, meli=None, config=None ):

        warningobj = self.env['meli.warning']
        context = self.env.context
        #import pdb;pdb.set_trace();
        _logger.info('[DEBUG] MercadoLibre Bind _product_post: ')
        _logger.info("self.env.context:" + str(context))
        force_meli_new_pub = context.get("force_meli_new_pub")
        force_meli_new_price = context.get("force_meli_new_price")
        force_meli_new_pricelist = context.get("force_meli_new_pricelist")
        force_meli_new_title = context.get("force_meli_new_title")
        _logger.info("self.env.context force_meli_new_pub:" + str(force_meli_new_pub))

        #binded title setting (use name or meli_title)
        if bind_tpl:
            bind_tpl.meli_title = force_meli_new_title or bind_tpl.meli_title or bind_tpl.name
            if bind:
                bind.name = bind_tpl.name
                bind.meli_title = bind_tpl.meli_title
            _logger.info("bind_tpl.meli_title: "+str(bind_tpl.meli_title))

        if bind:
            bind.meli_title = force_meli_new_title or bind.meli_title or bind.name
            _logger.info("bind.meli_title: "+str(bind.meli_title))


        www_cats = False
        if 'product.public.category' in self.env:
            www_cats = self.env['product.public.category']

        product_obj = self.env['product.product']
        product_tpl_obj = self.env['product.template']
        product = (bind and bind.product_id) or self
        product_tmpl = product and product.product_tmpl_id
        company = self.env.user.company_id
        if not config:
            config = company
        warningobj = self.env['meli.warning']

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company)
            if meli.need_login():
                return meli.redirect_login()

        #import pdb;pdb.set_trace();
        _logger.info('[DEBUG] product_post')
        _logger.info("self.env.context:" + str(self.env.context))

        www_cats = False
        if 'product.public.category' in self.env:
            www_cats = self.env['product.public.category']

        product_obj = self.env['product.product']
        product_tpl_obj = self.env['product.template']
        product = self
        product_tmpl = self.product_tmpl_id
        company = self.env.user.company_id
        if not config:
            config = company
        warningobj = self.env['meli.warning']

        account = bind and bind.connection_account
        company = (account and account.company_id) or company
        config = config or (account and account.configuration) or company

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                return meli.redirect_login()

        #return {}
        #description_sale =  product_tmpl.description_sale
        translation = self.env['ir.translation'].search([('res_id','=',product_tmpl.id),
                                                        ('name','=','product.template,description_sale'),
                                                        ('lang','=','es_AR')])
        if translation:
            #_logger.info("translation")
            #_logger.info(translation.value)
            description_sale = translation.value

        productjson = False

        #meli_id, id of the ML publication destination, if None, create a new publication
        if force_meli_new_pub:
            meli_id = None
        else:
            meli_id = (bind and bind.conn_id) or (bind_tpl and bind_tpl.conn_id) or product.meli_id

        _logger.info("_product_post meli_id is: "+str(meli_id))

        if (meli_id):
            response = meli.get("/items/%s" % str(meli_id), {'access_token':meli.access_token})
            if (response):
                productjson = response.json()

        #product_json is the data json Object from ML, use this data to update

        #translate everything to be compatible with bindings parameters
        #.....
        #se traduce muchos product. por bind.
        #luego se toman ciertos datos de product. y se los pasa a bind.
        #funcion que pasa entonces todos los parametros necesarios de product. a bind. (los seleccionados/clasicos por el usuario??)

        self._product_post_set_basic_configuration( product_tmpl=product_tmpl, meli=meli, config=config )

        source = product_tmpl
        target = product

        if bind_tpl and bind:
            #Cascading template configurations
            _logger.info("Setting binding template from product template.")
            res = self._product_post_set_template_configuration( product_tmpl=product_tmpl, product=bind_tpl, meli=meli, config=config )
            _logger.info("Setting binding variant from binding template.")
            res = self._product_post_set_template_configuration( product_tmpl=bind_tpl, product=bind, meli=meli, config=config )

            #match for vpub as variant
            bind_tpl.meli_pub_as_variant = product_tmpl.meli_pub_as_variant
            bind_tpl.meli_pub_principal_variant = product_tmpl.meli_pub_principal_variant
            #bind_tpl.meli_pub_principal_variant = source.meli_pub_principal_variant
            bind_tpl.meli_pub_variant_attributes = product_tmpl.meli_pub_variant_attributes

            source = bind_tpl
            target = bind
        else:
            res = self._product_post_set_template_configuration( product_tmpl=product_tmpl, product=product, meli=meli, config=config )

        _logger.info("source: "+str(source)+str(source.display_name)+" target: "+str(target)+str(target.name))
        self._product_post_set_title( meli_title=force_meli_new_title, source_tmpl=source, target=target, meli=meli, config=config )

        #revisar regla e precio
        product and product.set_meli_price( meli=meli, config=config)
        #target.price = product.meli_price
        if force_meli_new_price and target and target.meli_currency!="MXN":
            force_meli_new_price = str(int(float(force_meli_new_price)))
        _logger.info("force_meli_new_price: "+str(force_meli_new_price))
        self._product_post_set_price( meli_price=force_meli_new_price, meli_pricelist=force_meli_new_pricelist, source_tmpl=source, target=target, meli=meli, config=config )
        _logger.info("source.meli_price: "+str(source and source.meli_price))
        _logger.info("target.meli_price: "+str(target and target.meli_price))

        attributes = self._product_post_set_attributes( product_tmpl=source, product=target, meli=meli, config=config )
        self._product_post_set_category( product_tmpl=source, product=target, meli=meli, config=config )
        meli_id = target.meli_id or ("conn_id" in target._fields and target.conn_id)
        #if meli_id is false, publish on base product
        self._product_post_set_quantity( target=target, product=product, meli_id=meli_id, meli=meli, config=config )

        #TODO: publicando imagenes
        first_image_to_publish = get_first_image_to_publish( product )
        #if (productjson and "pictures" in productjson):
        #    product._meli_remove_images_unsync( product_tmpl, productjson["pictures"] )

        if first_image_to_publish==None:
            raise ValidationError("Debe cargar una imagen de base en el producto, si chequeo el 'Dont use first image' debe al menos poner una imagen adicional en el producto.")
            #return warningobj.info( title='MELI WARNING', message="Debe cargar una imagen de base en el producto, si chequeo el 'Dont use first image' debe al menos poner una imagen adicional en el producto.", message_html="" )
        else:
            # _logger.info( "try uploading image..." )
            resim = product.product_meli_upload_image( bind_tpl=bind_tpl, meli=meli, config=config )
            _logger.info("resim: " +str(resim))
            if "status" in resim:
                if (resim["status"]=="error" or resim["status"]=="warning"):
                    error_msg = 'MELI: mensaje de error:   ', resim
                    _logger.error(error_msg)
                    if (resim["status"]=="error"):
                        #raise ValidationError("Problemas cargando la imagen principal. Imagen principal faltante.")
                        self.env.cr.rollback()
                        return warningobj.info( title='MELI WARNING', message="Problemas cargando la imagen principal.", message_html=error_msg, context= { 'rjson': resim } )
                else:
                    assign_img = True and product.meli_imagen_id
            if bind and not bind.meli_imagen_id:
                bind.meli_imagen_id = product.meli_imagen_id
                _logger.info("bind.meli_imagen_id: " +str(bind.meli_imagen_id))

        meli_imagen_id = (bind and bind.meli_imagen_id) or product.meli_imagen_id
        #FIN IMAGEN PRINCIPAL

        #publicando multiples imagenes: TODO use bind images
        multi_images_ids = {}
        if (variant_image_ids(product) or template_image_ids(product)):
            multi_images_ids = product.product_meli_upload_multi_images(meli=meli,config=config)
            _logger.info(multi_images_ids)
            if 'status' in multi_images_ids:
                _logger.error(multi_images_ids)
                self.env.cr.rollback()
                #return warningobj.info( title='MELI WARNING', message="Error publicando imagenes", message_html="Error: "+str(("error" in multi_images_ids and multi_images_ids["error"]) or "")+" Status:"+str(("status" in multi_images_ids and multi_images_ids["status"]) or "") )
                return warningobj.info( title='MELI WARNING', message="Error publicando imagenes", message_html="Error: "+str(multi_images_ids), context = { 'rjson': resim } )
                #raise ValidationError("Error publicando multiples imagenes")


        meli_multi_imagen_id = multi_images_ids or product.meli_multi_imagen_id
        #FIN IMAGENES PRINCIPAL

        body, bodydescription = self._product_post_set_body( product_tmpl=source, product=target, meli=meli, config=config,
                                                             attributes=attributes,
                                                             meli_imagen_id=meli_imagen_id,
                                                             meli_multi_imagen_id=meli_multi_imagen_id,
                                                             productjson=productjson )

        #if target
        body = self._product_set_variations( product_tmpl=product_tmpl,
                                                product=product,
                                                bind_tpl=bind_tpl,
                                                meli=meli,
                                                config=config,
                                                attributes=attributes,
                                                productjson=productjson,
                                                body=body,
                                                bodydescription=bodydescription )

        if meli_id:
            _logger.info("update post:"+str(body))
            response = meli.put("/items/"+str(meli_id), body, {'access_token':meli.access_token})
        else:
            assign_img = True and product.meli_imagen_id
            _logger.info("first post:" + str(body)+" meli: login_id: "+str(meli.meli_login_id)+" client_id: "+str(meli.client_id)+" seller_id: "+str(meli.seller_id)+" access_token: "+str(meli.access_token))
            response = meli.post("/items", body, {'access_token':meli.access_token})

        rjson = response.json()
        _logger.info(rjson)

        #check error
        if "error" in rjson:
            #error_msg = '<h6>Mensaje de error de MercadoLibre: %s; status: %s </h6><h2>Mensaje: %s</h2><br/><h6>Cause: </h6> %s' % (rjson["error"], rjson["status"], rjson["message"], rjson["cause"])
            error_msg = '<h6>Mensaje de error de MercadoLibre</h6><br/><h2>Mensaje: %s</h2><br/><h6>Status</h6> %s<br/><h6>Cause</h6> %s<br/><h6>Error completo:</h6><br/><span>%s</span><br/>' % (rjson["message"], rjson["status"], rjson["cause"], rjson["error"])
            _logger.error(error_msg)
            if (rjson["cause"] and rjson["cause"][0] and "message" in rjson["cause"][0]):
                error_msg+= '<h3>'+str(rjson["cause"][0]["message"])+'</h3>'
            #expired token
            if "message" in rjson and (rjson["error"]=="forbidden" or rjson["message"]=='invalid_token' or rjson["message"]=="expired_token"):
                url_login_meli = meli.auth_url()
                self.env.cr.rollback()
                #raise ValidationError("Debe iniciar sesión en MELI:  "+str(rjson["message"]))
                return warningobj.info( title='MELI WARNING', message="Debe iniciar sesión en MELI:  "+str(rjson["message"]), message_html="<br><br>"+error_msg, context = { 'rjson': rjson })
            else:
                #Any other errors
                self.env.cr.rollback()
                #raise ValidationError("Recuerde completar todos los campos y revise el mensaje siguiente."+str(error_msg))
                return warningobj.info( title='MELI WARNING', message="Recuerde completar todos los campos y revise el mensaje siguiente.", message_html="<br><br>"+error_msg, context = { 'rjson': rjson } )

        #last modifications if response is OK
        if "id" in rjson:
            meli_id = rjson["id"]
            if meli_id and bodydescription:
                resdescription = meli.put("/items/"+str(meli_id)+"/description", bodydescription, {'access_token':meli.access_token})
                rjsondes = resdescription.json()

                _logger.info("rjsondes: "+str(rjsondes))
                if "error" in rjsondes:
                    self.env.cr.rollback()
                    return warningobj.info( title='MELI WARNING', message="Error en la descripción", message_html="", context = { 'rjson': rjsondes })


            if bind and bind_tpl:
                _logger.info("Last updates: binded publication")
                bind_tpl.write( { 'conn_id': rjson["id"]} )
                bind.write( { 'meli_id': rjson["id"],'conn_id': rjson["id"]} )
                #WARNING IF NEW PUB with variants, must call product_template_rebind, to create all variant binding too
            else:
                _logger.info("Last updates: base product publication")
                target.write( { 'meli_id': rjson["id"]} )
                #TODO: check variations
                if ("variations" in rjson):
                    _logger.info("Check variations:"+str(len(rjson["variations"])))
                    for ix in range(len(rjson["variations"]) ):
                        _var = rjson["variations"][ix]
                        for pvar in product_tmpl.product_variant_ids:
                            if (pvar._is_product_combination(_var) and 'id' in _var):
                                pvar.meli_id_variation = _var["id"]
                                pvar.meli_id = rjson["id"]

        if bind and bind_tpl:
            rebind_needed = bind_tpl.variant_bindings and product_tmpl.product_variant_ids and len(bind_tpl.variant_bindings) != len(product_tmpl.product_variant_ids)
            _logger.info("Rebind needed:"+str(rebind_needed))
            if force_meli_new_pub or rebind_needed:
                _logger.info("Rebind needed or forced: force_meli_new_pub:"+str(force_meli_new_pub))
                bind_tpl.product_template_rebind()
            if "id" in rjson:
                bind_tpl.copy_from_rjson( rjson=rjson, meli=meli )

            stock = 0
            bind_tpl.price = bind_tpl.price or product_tmpl.meli_price
            for bindv in bind_tpl.variant_bindings:
                bindv.meli_available_quantity = (bindv.product_id and bindv.product_id.meli_available_quantity) or 0
                bindv.price = bind_tpl.price
                bindv.stock = bindv.meli_available_quantity
                stock+= bindv.stock
            bind_tpl.stock = stock
            #bind.copy_from_rjson( rjson=rjson, meli=meli )
        else:
            for bindT in product_tmpl.mercadolibre_bindings:
                if (bindT.conn_id==target.meli_id):
                    rebind_needed = target.meli_pub_as_variant and bindT.variant_bindings and product_tmpl.product_variant_ids and len(bindT.variant_bindings) != len(product_tmpl.product_variant_ids)
                    _logger.info("Rebind needed:"+str(rebind_needed))
                    if force_meli_new_pub or rebind_needed:
                        _logger.info("Rebind needed or forced: force_meli_new_pub:"+str(force_meli_new_pub))
                        bindT.product_template_rebind()
                    if "id" in rjson:
                        bindT.copy_from_rjson( rjson=rjson, meli=meli )
                    stock = 0
                    bindT.price = bindT.price or product_tmpl.meli_price
                    for bindv in bindT.variant_bindings:
                        bindv.meli_available_quantity = (bindv.product_id and bindv.product_id.meli_available_quantity) or 0
                        bindv.stock = bindv.meli_available_quantity
                        bindv.meli_price = bindv.product_id.meli_price
                        bindv.price = bindv.meli_price
                        stock+= bindv.stock
                    bindT.stock = stock


        #raise ValidationError(str(rjson)+str(body))

        #TODO: check target activation
        force_meli_active = False
        if ("force_meli_active" in self.env.context):
            force_meli_active = self.env.context.get("force_meli_active")
        if (force_meli_active==True):
            target.product_meli_status_active()

        return {}


    def product_post(self, bind_tpl=None, bind=None, meli=None, config=None ):
        res = []
        for product in self:
            res.append(product._product_post( bind_tpl=bind_tpl, bind=bind, meli=meli, config=config ))

        return res

    def product_get_meli_update( self ):

        _logger.info("meli_oerp_multiple >> product_get_meli_update")

        company = self.env.user.company_id
        warningobj = self.env['meli.warning']
        product_obj = self.env['product.product']

        ML_status = "unknown"
        ML_sub_status = ""
        ML_permalink = ""
        ML_state = False
        #meli = None
        product = self
        product.meli_status = ML_status
        product.meli_sub_status = ML_sub_status
        product.meli_permalink = ML_permalink
        product.meli_state = ML_state
        return {}

        #meli = self.env['meli.util'].get_new_instance(company)

        if meli and meli.need_login():
            ML_status = "unknown"
            ML_permalink = ""
            ML_state = True

        for product in self:
            if product.meli_id and meli and not meli.need_login():
                response = meli.get("/items/"+product.meli_id, {'access_token':meli.access_token} )
                rjson = response.json()
                if "status" in rjson:
                    ML_status = rjson["status"]
                if "permalink" in rjson:
                    ML_permalink = rjson["permalink"]
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
            product.meli_state = ML_state

    def x_match_variation_id( self, meli=None, meli_id=None, meli_id_variation=None, product_sku=None ):
        #return  same variation id existing matched with sku, or first matched with sku
        target_meli_id_variation = None
        _logger.info("x_match_variation_id")
        productjson = self.env["mercadolibre.account"].fetch_meli_product( meli_id=meli_id, meli=meli )
        if ( productjson and "variations" in productjson and len(productjson["variations"]) ):
            #varias = {
            #    "variations": []
            #}
            _logger.info("x_match_variation_id product_post_stock > Update variations stock")
            found_comb = False
            #pictures_v = []
            #same_price = False
            #TODO: check combination now based on SKU and forget!!
            for ix in range(len(productjson["variations"]) ):
                vr = productjson["variations"][ix]
                seller_sku = ("seller_sku" in vr and vr["seller_sku"]) or ("seller_custom_field" in vr and vr["seller_custom_field"])
                #check if combination is related to this product
                #if 'picture_ids' in productjson["variations"][ix]:
                #    if (len(productjson["variations"][ix]["picture_ids"])>len(pictures_v)):
                #        pictures_v = productjson["variations"][ix]["picture_ids"]
                #same_price = productjson["variations"][ix]["price"]
                #_logger.info(productjson["variations"][ix])
                if (seller_sku==product_sku):# or self._is_product_combination(productjson["variations"][ix])):
                    _logger.info("x_match_variation_id _is_product_combination! Post stock to variation")
                    #_logger.info(productjson["variations"][ix])
                    found_comb = True
                    #reset meli_id_variation (TODO: resetting must be done outside)
                    target_meli_id_variation = productjson["variations"][ix]["id"]
                    #if target:
                        #WARNING; will change the publication id variation?
                    #    if (str(target.conn_variation_id)!=str(target_meli_id_variation)):
                    #        reserror =  { "error": "Changing binding variant meli_id:"+str(target.conn_id)+" conn_id_variation: " + str(target.conn_variation_id) + " target_meli_id_variation: " + str(target_meli_id_variation) }
                    #        _logger.error(reserror)
                            #return reserror
                    #    target.meli_id_variation = str(target_meli_id_variation)
                    #    target.conn_variation_id = str(target_meli_id_variation)
                    #var = {
                        #"id": str( product.meli_id_variation ),
                    #    "available_quantity": product.meli_available_quantity,
                        #"picture_ids": ['806634-MLM28112717071_092018', '928808-MLM28112717068_092018', '643737-MLM28112717069_092018', '934652-MLM28112717070_092018']
                    #}
                    #varias["variations"].append(var)
                    #_logger.info(varias)
                    #_logger.info(var)
                    #responsevar = meli.put("/items/"+str(meli_id)+'/variations/'+str( target_meli_id_variation ), var, {'access_token':meli.access_token})
                    #_logger.info(responsevar.json())
                    #if responsevar:
                    #    rjson = responsevar.json()
                    #    if rjson:
                    #        if "error" in rjson:
                    #            _logger.error(rjson)
                    #            return rjson
        return target_meli_id_variation


    def x_product_post_stock( self, context=None, meli=False, config=None, meli_id=None, meli_id_variation=None, target=None ):
        context = context or self.env.context
        _logger.info("meli_oerp product_post_stock x_product_post_stock context: " + str(context)+" meli:"+str(meli)
                        +" config:"+str(config)
                        +" meli_id:"+str(meli_id)
                        +" meli_id_variation:"+str(meli_id_variation)
                        +" target:"+str(target and target.name)
                        )
        company = self.env.user.company_id
        warningobj = self.env['meli.warning']

        product_obj = self.env['product.product']
        product = self
        product_tmpl = self.product_tmpl_id
        config = config or company
        meli_id = meli_id or product.meli_id
        is_fulfillment = False
        
        if "meli_update_stock_blocked" in product_tmpl._fields and product_tmpl.meli_update_stock_blocked:
            error = { "error": "Blocked by product template configuration." }
            product.meli_stock_error = str(error)
            product_tmpl.meli_stock_error = product.meli_stock_error
            product.message_post(body=str(error["error"]),message_type=product_message_type)
            product_tmpl.message_post(body=str(error["error"]),message_type=product_message_type)
            return error

        if "meli_update_stock_blocked" in product._fields and product.meli_update_stock_blocked:
            error = { "error": "Blocked by product configuration." }
            product.meli_stock_error = str(error)
            product_tmpl.meli_stock_error = product.meli_stock_error
            product.message_post(body=str(error["error"]),message_type=product_message_type)
            product_tmpl.message_post(body=str(error["error"]),message_type=product_message_type)
            return error

        if not meli or not hasattr(meli, 'client_id'):
            _logger.error("x_product_post_stock meli not set")
            meli = self.env['meli.util'].get_new_instance(company)
            if meli.need_login():
                return meli.redirect_login()

        try:
            #self.product_update_stock()
            product_fab = False
            if (1==1 and product.virtual_available<=0 and product.route_ids):
                for route in product.route_ids:
                    if (route.name in ['Fabricar','Manufacture']):
                        _logger.info("Fabricar: "+str(product.meli_available_quantity))
                        product_fab = True

            #_logger.info("Update master product stock:"+str(product.meli_id))
            if (not product_fab):
                product.meli_available_quantity = product._meli_available_quantity( meli_id=product.meli_id, meli=meli, config=config )

            if product.meli_available_quantity<0:
                product.meli_available_quantity = 0
            #_logger.info("Update master product stock:"+str(product.meli_available_quantity))

            #is_fulfillment based on target or product

            is_target_fulfillment = ( target and target.meli_shipping_logistic_type and "fulfillment" in target.meli_shipping_logistic_type )
            is_product_fulfillment = ( product.meli_shipping_logistic_type and "fulfillment" in product.meli_shipping_logistic_type )

            #if the target is fulfillment do not process the all thing
            #target null means the product is the target...
            is_fulfillment = is_target_fulfillment or (not target and is_product_fulfillment)
            if is_fulfillment:
                _logger.info("is_fulfillment: "+str(is_fulfillment))
                return { "error": "fulfillment" }

            if product:
                qty = product.meli_available_quantity
            if target:
                qty = target.meli_available_quantity

            fields = {
                "available_quantity": qty
            }

            #_logger.info("post stock:"+str(product.meli_available_quantity))
            #_logger.info("product_tmpl.meli_pub_as_variant:"+str(product_tmpl.meli_pub_as_variant))
            #_logger.info(product_tmpl.meli_pub_principal_variant.id)
            if (product_tmpl.meli_pub_as_variant):
                productjson = False
                if (product_tmpl.meli_pub_principal_variant.id==False and len(product_tmpl.product_variant_ids)):
                    product_tmpl.meli_pub_principal_variant = product_tmpl.product_variant_ids[0]

                if (product_tmpl.meli_pub_principal_variant):
                    base_meli_id = meli_id or product_tmpl.meli_pub_principal_variant.meli_id
                    if (base_meli_id):
                        #response = meli.get("/items/%s" % base_meli_id, {'access_token':meli.access_token, 'include_attributes': 'all'})
                        #if (response):
                        #    productjson = response.json()
                        productjson = self.env["mercadolibre.account"].fetch_meli_product( meli_id=base_meli_id, meli=meli )
                        #_logger.info("productjson:"+str(productjson))

                #chequeamos la variacion de este producto
                if ( productjson and "variations" in productjson and len(productjson["variations"]) ):
                    varias = {
                        "variations": []
                    }
                    _logger.info("x_product_post_stock product_post_stock > Update variations stock")
                    found_comb = False
                    pictures_v = []
                    same_price = False
                    #TODO: check combination now based on SKU and forget!!
                    for ix in range(len(productjson["variations"]) ):
                        vr = productjson["variations"][ix]
                        seller_sku = ("seller_sku" in vr and vr["seller_sku"]) or ("seller_custom_field" in vr and vr["seller_custom_field"])
                        #check if combination is related to this product
                        if 'picture_ids' in productjson["variations"][ix]:
                            if (len(productjson["variations"][ix]["picture_ids"])>len(pictures_v)):
                                pictures_v = productjson["variations"][ix]["picture_ids"]
                        same_price = productjson["variations"][ix]["price"]
                        #_logger.info(productjson["variations"][ix])
                        if (seller_sku==product.default_code or self._is_product_combination(productjson["variations"][ix])):
                            #_logger.info("x_product_post_stock _is_product_combination! Post stock to variation")
                            #_logger.info(productjson["variations"][ix])
                            found_comb = True
                            #reset meli_id_variation (TODO: resetting must be done outside)
                            target_meli_id_variation = productjson["variations"][ix]["id"]
                            if target:
                                #WARNING; will change the publication id variation?
                                reserror = None
                                if (str(target.conn_variation_id)!=str(target_meli_id_variation)):
                                    if (seller_sku==product.default_code):
                                        reserror =  { "warning": "Changing binding variant meli_id:"+str(target.conn_id)+" conn_id_variation: " + str(target.conn_variation_id) + " TO target_meli_id_variation: " + str(target_meli_id_variation)+" internal:"+str(product.default_code) }
                                        _logger.warning(reserror)
                                    else:
                                        reserror =  { "error": "Changing binding variant meli_id:"+str(target.conn_id)+" conn_id_variation: " + str(target.conn_variation_id) + " TO target_meli_id_variation: " + str(target_meli_id_variation)+" different seller_sku! Need to check! "+" internal:"+str(product.default_code)+" vs seller_sku:"+str(seller_sku) }
                                        _logger.error(reserror)
                                        return reserror
                                try:

                                    target.meli_id_variation = str(target_meli_id_variation)
                                    target.conn_variation_id = str(target_meli_id_variation)
                                except Exception as e:
                                    if reserror:
                                        _logger.error(str(e))
                                        _logger.error(reserror)
                                        return reserror
                                    else:
                                        reserror = { "error": str(e) }
                                        _logger.error(reserror)
                                        return reserror


                            #update base product qty
                            product.meli_available_quantity = product._meli_available_quantity( meli_id=product.meli_id, meli=meli, config=config )
                            meli_id_stock = product.meli_available_quantity

                            #update target binding qty (target!=product)
                            if (target and meli_id and meli_id!=product.meli_id):
                                meli_id_stock = product._meli_available_quantity( meli_id=meli_id, meli=meli, config=config )
                                target.meli_available_quantity = meli_id_stock

                            var = {
                                #"id": str( product.meli_id_variation ),
                                "available_quantity": meli_id_stock,
                                #"picture_ids": ['806634-MLM28112717071_092018', '928808-MLM28112717068_092018', '643737-MLM28112717069_092018', '934652-MLM28112717070_092018']
                            }
                            varias["variations"].append(var)
                            #_logger.info(varias)
                            #_logger.info(var)
                            responsevar = meli.put("/items/"+str(meli_id)+'/variations/'+str( target_meli_id_variation ), var, {'access_token':meli.access_token})
                            #_logger.info(responsevar.json())
                            if responsevar:
                                #_logger.info(responsevar.json())
                                rjson = responsevar.json()
                                if rjson:
                                    if "error" in rjson:
                                        _logger.error(rjson)
                                        return rjson
                            #_logger.info("x_product_post_stock: No error")

                    if found_comb==False and 1==2:
                        #add combination!!
                        #_logger.info("add combination")
                        addvar = self._combination()
                        #_logger.info(addvar)
                        if addvar:
                            if ('picture_ids' in addvar):
                                if len(pictures_v)>=len(addvar["picture_ids"]):
                                    addvar["picture_ids"] = pictures_v
                            #if (config.mercadolibre_post_default_code): #TODO: fixing SKU must be specific parameter
                            #    addvar["seller_custom_field"] = product.default_code
                            addvar["price"] = same_price
                            #_logger.info("Add variation!")
                            #_logger.info(addvar)
                            responsevar = meli.post("/items/"+str(meli_id)+"/variations", addvar, {'access_token':meli.access_token})
                            if responsevar:
                                rjson = responsevar.json()
                                _logger.info(responsevar.json())
                                if rjson:
                                    if "error" in rjson:
                                        _logger.error(rjson)
                                        return rjson
                            #_logger.info(responsevar.json())
                #_logger.info("Available:"+str(product_tmpl.virtual_available))
                best_available = 0

                #TEST AND PAUSE OR ACTIVATE (product)
                for vr in product_tmpl.product_variant_ids:
                    sum = vr.meli_available_quantity
                    if (sum<0):
                        sum = 0
                    best_available+= sum
                if (best_available>0 and product.meli_status=="paused"):
                    _logger.info("x_product_post_stock > Active! product:"+str(product.meli_id))
                    product.product_meli_status_active(meli=meli)
                elif (best_available<=0 and product.meli_status=="active"):
                    _logger.info("x_product_post_stock > Pause! product:"+str(product.meli_id))
                    #product.product_meli_status_pause(meli=meli)

                #TEST AND PAUSE OR ACTIVATE (target=binding)
                if target:
                    for vr in target.binding_product_tmpl_id.variant_bindings:
                        pvr = vr.product_id
                        if pvr:
                            vr.meli_available_quantity = pvr._meli_available_quantity( meli_id=vr.meli_id, meli=meli, config=config )
                        sum = vr.meli_available_quantity
                        if (sum<0):
                            sum = 0
                        best_available+= sum
                    if (best_available>0 and target.meli_status=="paused"):
                        _logger.info("x_product_post_stock > Active! target:"+str(target.meli_id))
                        target.product_meli_status_active(meli=meli)
                    elif (best_available<=0 and target.meli_status=="active"):
                        _logger.info("x_product_post_stock > Pause! target:"+str(target.meli_id))
                        #target.product_meli_status_pause(meli=meli)
            else:
                if (meli_id and not meli_id_variation):
                    #_logger.info("meli:"+str(meli))
                    response = meli.get("/items/%s" % meli_id, {'access_token':meli.access_token})
                    if (response):
                        pjson = response.json()
                        if "variations" in pjson:
                            if (len(pjson["variations"])==1):
                                meli_id_variation = pjson["variations"][0]["id"]

                                if (target and target.conn_id==meli_id and target.meli_id==meli_id):
                                    _logger.info("fix bind variant meli_id_variation: "+str(meli_id_variation))
                                    target.conn_variation_id = meli_id_variation
                                    target.meli_id_variation = meli_id_variation

                                if (product.meli_id==meli_id and product.meli_id_variation != meli_id_variation):
                                    _logger.info("fix product meli_id_variation: "+str(meli_id_variation))
                                    product.meli_id_variation = meli_id_variation

                if (meli_id_variation):
                    _logger.info("Posting using product.meli_id_variation")
                    #check if variation id exists in target
                    response = meli.get("/items/%s/variation/%s" % (meli_id,meli_id_variation), {'access_token':meli.access_token})
                    if (response):
                        pjson = response.json()
                        if pjson and "error" in pjson:
                            fix_meli_id_variation = self.x_match_variation_id(meli=meli, meli_id=meli_id, meli_id_variation=meli_id_variation, product_sku=product.default_code )
                            if not fix_meli_id_variation:
                                verror = { "error": "Variation id not found for sku %s in (%s,%s) " % (str(product.default_code), meli_id, meli_id_variation ) }
                                _logger.error(verror)
                                return verror

                            meli_id_variation = fix_meli_id_variation

                    meli_id_stock = product.meli_available_quantity

                    #update target binding qty (target!=product)
                    if (target and meli_id and meli_id!=product.meli_id):
                        meli_id_stock = product._meli_available_quantity( meli_id=meli_id, meli=meli, config=config )
                        target.meli_available_quantity = meli_id_stock

                    var = {
                        #"id": str( product.meli_id_variation ),
                        "available_quantity": meli_id_stock,
                        #"picture_ids": ['806634-MLM28112717071_092018', '928808-MLM28112717068_092018', '643737-MLM28112717069_092018', '934652-MLM28112717070_092018']
                    }
                    responsevar = meli.put("/items/"+meli_id+'/variations/'+str( meli_id_variation ), var, {'access_token':meli.access_token})
                    if (responsevar):
                        rjson = responsevar.json()
                        if rjson:
                            _logger.info(rjson)
                            if "error" in rjson:
                                _logger.error(rjson)
                                return rjson
                            if ('available_quantity' in rjson):
                                _logger.info( "Posted ok:" + str(rjson['available_quantity']) )
                else:
                    response = meli.put("/items/"+meli_id, fields, {'access_token':meli.access_token})
                    if (response):
                        rjson = response.json()
                        if rjson and "error" in rjson:
                            _logger.error(rjson)
                            return rjson
                        if (rjson and 'available_quantity' in rjson):
                            _logger.info( "Posted ok:" + str(rjson['available_quantity']) )

                if (product.meli_available_quantity<=0 and product.meli_status=="active"):
                    #product.product_meli_status_pause(meli=meli)
                    _logger.info("Pause (not)")
                elif (product.meli_available_quantity>0 and product.meli_status=="paused"):
                    product.product_meli_status_active(meli=meli)

                if (target.meli_available_quantity<=0 and target.meli_status=="active"):
                    #target.product_meli_status_pause(meli=meli)
                    _logger.info("Pause (not)")
                elif (target.meli_available_quantity>0 and target.meli_status=="paused"):
                    target.product_meli_status_active(meli=meli)

        except Exception as e:
            _logger.info("x_product_post_stock > exception error")
            _logger.info(e, exc_info=True)
            pass;
         #_logger.info("x_product_post_stock > ended")
        return {}

    def product_post_stock( self, context=None, meli=False, config=None ):

        context = context or self.env.context
        #_logger.info("meli_oerp_multiple product_post_stock context: " + str(context))
        company = self.env.user.company_id
        warningobj = self.env['meli.warning']

        product_obj = self.env['product.product']
        product = self
        product_tmpl = self.product_tmpl_id

        if not config or not meli:
            for bind in product.mercadolibre_bindings:
                bind.product_post_stock(meli=meli)
            return {}

        config = config or company

        if not meli or not hasattr(meli, 'client_id'):
            meli = self.env['meli.util'].get_new_instance(company)
            if meli.need_login():
                return meli.redirect_login()

        meli_id = product.meli_id
        meli_id_variation = product.meli_id_variation

        return product.x_product_post_stock(context=context,meli=meli, config=config, meli_id=meli_id, meli_id_variation=meli_id_variation )

    def x_product_post_price( self, meli_price=None, meli_currency=None, context=None, meli=False, config=None, meli_id=None, meli_id_variation=None ):
        company = self.env.user.company_id
        warningobj = self.env['meli.warning']

        product_obj = self.env['product.product']
        product = self
        product_tmpl = self.product_tmpl_id

        if not meli:
            meli = self.env['meli.util'].get_new_instance(company)
            if meli.need_login():
                return meli.redirect_login()

        product.set_meli_price( config=config )

        meli_price = meli_price or product.meli_price
        meli_currency = meli_currency or product.meli_currency or product_tmpl.meli_currency
        _logger.info("meli_currency:"+str(meli_currency))

        fields = {
            "price": meli_price
        }

        fields_cur = {}

        pjson = False

        if (meli_id):
            response = meli.get("/items/%s" % (str(meli_id)), {'access_token':meli.access_token})
            if (response):
                pjson = response.json()

        if pjson and "currency_id" in pjson:
            if meli_currency and str(pjson["currency_id"])!=str(meli_currency):
                fields_cur = {
                    "currency_id": meli_currency
                }
                fields.update(fields_cur)

        if (meli_id and not meli_id_variation and pjson):
            #_logger.info("meli:"+str(meli))
            if "variations" in pjson:
                if (len(pjson["variations"])==1):
                    meli_id_variation = pjson["variations"][0]["id"]

        if (meli_id_variation and pjson):
            if "variations" in pjson:
                vars = []
                for varx in pjson["variations"]:
                #_logger.info("Posting using product.meli_id_variation")
                    var = {
                        "id": varx["id"],
                        "price": meli_price,
                        #"picture_ids": ['806634-MLM28112717071_092018', '928808-MLM28112717068_092018', '643737-MLM28112717069_092018', '934652-MLM28112717070_092018']
                    }
                    vars.append(var)
                _logger.info("product_post_price (variations):"+str(vars))

                fields = { "variations": vars }
                if fields_cur:
                    fields.update(fields_cur)
                _logger.info("product_post_price (variations): fields: "+str(fields))

                #responsevar = meli.put("/items/"+str(meli_id)+'/variations/'+str( meli_id_variation ), var, {'access_token':meli.access_token})
                responsevar = meli.put("/items/"+str(meli_id), fields, {'access_token':meli.access_token})
                if (responsevar):
                    rjson = responsevar.json()
                    if rjson:
                        #_logger.info('rjson'+str(rjson))
                        if "error" in rjson:
                            _logger.error(rjson)
                            return rjson
                        if ('price' in rjson):
                            _logger.info( "Posted price ok (variations)" + str(meli_id) + ": " + str(rjson['price']) )
                        else:
                            _logger.info( "Posted price ok (variations)" + str(meli_id) + ": " + str('variations' in rjson and rjson['variations']))


        else:
            _logger.info("product_post_price (single):"+str(fields))
            response = meli.put("/items/"+str(meli_id), fields, {'access_token':meli.access_token})
            if response:
                rjson = response.json()
                if rjson and "error" in rjson:
                    _logger.error(rjson)
                    return rjson
                _logger.info( "Posted price ok (single)" + str(rjson))
                if (rjson and len(rjson) and 'price' in rjson):
                    _logger.info( "Posted price ok (single)" + str(meli_id) + ": " + str(rjson['price']) )
        return {}

    def product_post_price( self, context=None, meli=False, config=None ):

        context = context or self.env.context
        _logger.info("meli_oerp_multiple product_post_price context: " + str(context))
        company = self.env.user.company_id
        warningobj = self.env['meli.warning']

        product_obj = self.env['product.product']
        product = self
        product_tmpl = self.product_tmpl_id


        if not config or not meli:
            for bind in product.mercadolibre_bindings:
                bind.product_post_price(meli=meli)
            return {}
        #standard version meli_oerp
        config = config or company


        if not meli or not hasattr(meli, 'client_id'):
            meli = self.env['meli.util'].get_new_instance(company)
            if meli.need_login():
                return meli.redirect_login()

        meli_id = product.meli_id
        meli_id_variation = product.meli_id_variation

        return product.x_product_post_price(context=context,meli=meli, config=config, meli_id=meli_id, meli_id_variation=meli_id_variation )

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
                #update product meli_shipping_logistic_type if meli_id binding match the base product
                product.meli_shipping_logistic_type = meli_shipping_logistic_type

            #Update meli_shipping_logistic_type for all meli_id bindings and parent binding template
            bindings = self.env["mercadolibre.product"].search( [ ('product_id','=' ,product.id ), ('conn_id','=' ,str(meli_id) )] )
            for bind in bindings:
                bind.meli_shipping_logistic_type = meli_shipping_logistic_type
                bind.binding_product_tmpl_id.meli_shipping_logistic_type = meli_shipping_logistic_type

            return meli_shipping_logistic_type
        return ""




class PricelistItem(models.Model):

    _inherit = "product.pricelist.item"

    @api.onchange('applied_on', 'product_id', 'product_tmpl_id', 'min_quantity','price')
    def _meli_onchange_pricelist_item(self):
        #set meli_price_update to False
        for pli in self:
            if pli.product_tmpl_id:
                pli.product_tmpl_id.meli_price_update = False
                for bind_tpl in pli.product_tmpl_id.mercadolibre_bindings:
                    bind_tpl.price_update = False

                for var in pli.product_tmpl_id.product_variant_ids:
                    var.meli_price_update = False
                    for bind in var.mercadolibre_bindings:
                        bind.price_update = False

            if pli.product_id:
                pli.product_id.meli_price_update = False
                pli.product_id.product_tmpl_id.meli_price_update = False
                for bind in pli.product_id.mercadolibre_bindings:
                    bind.price_update = False
