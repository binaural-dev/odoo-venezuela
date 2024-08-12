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
###############################################*###############################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
import threading
#from .warning import warning
import requests
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
from . import versions
from .versions import *
from odoo.addons.meli_oerp.models.versions import *
import json
import base64

import hashlib
from datetime import datetime


class MercadoLibreBrand(models.Model):

    _name = 'mercadolibre.brand'
    _description = 'MercadoLibre Brand'

    name = fields.Char(string="Name",required=True,index=True)

    #https://api.mercadolibre.com/users/609389670/brands
    official_store_id = fields.Char(string="Official Store Id",required=True,index=True)
    site_id = fields.Char(string="Site Id",required=True,index=True)
    seller_id = fields.Char(string="Seller id",required=True,index=True)

    fantasy_name = fields.Char(string="Name",required=True,index=True)
    status = fields.Char(string="Status",required=True,index=True)
    type = fields.Char(string="Type",required=True,index=True)

    permalink = fields.Char(string="Permalink",required=True,index=True)


class MercadoLibreMaestro(models.Model):

    _name = 'mercadolibre.product.maestro'
    _description = 'MercadoLibre Product Maestro'

    connection_account = fields.Many2one("mercadolibre.account",string="Account")
    company_id = fields.Many2one("res.company",related="connection_account.company_id",string="Company")

    name = fields.Char(string="Name",required=True, index=True)
    description = fields.Char(string="Description",index=True)

    brand = fields.Char(string="Brand", index=True)
    model = fields.Char(string="Model", index=True)

    length = fields.Char(string="Length", index=True)
    height = fields.Char(string="Height", index=True)
    width = fields.Char(string="Width", index=True)
    weight = fields.Char(string="Weight", index=True)

    attributes = fields.Char(string="Atributos",index=True)

    sku = fields.Char(string="Sku",help="Referencia interna / Seller SKU",index=True)
    barcode = fields.Char(string="Barcode", help="Codigo de barras", index=True)

    barcode0 = fields.Char(string="Barcode0",help="LDM/Combo Barcode[0-10]",index=True)
    quantity0 = fields.Float(string="Quantity0")

    barcode1 = fields.Char(string="Barcode1",help="LDM/Combo Barcode[0-10]",index=True)
    quantity1 = fields.Float(string="Quantity1")

    barcode2 = fields.Char(string="Barcode2",help="LDM/Combo Barcode[0-10]",index=True)
    quantity2 = fields.Float(string="Quantity2")

    barcode3 = fields.Char(string="Barcode3",help="LDM/Combo Barcode[0-10]",index=True)
    quantity3 = fields.Float(string="Quantity3")

    barcode4 = fields.Char(string="Barcode4",help="LDM/Combo Barcode[0-10]",index=True)
    quantity4 = fields.Float(string="Quantity4")

    barcode5 = fields.Char(string="Barcode5",help="LDM/Combo Barcode[0-10]",index=True)
    quantity5 = fields.Float(string="Quantity5")

    barcode6 = fields.Char(string="Barcode6",help="LDM/Combo Barcode[0-10]",index=True)
    quantity6 = fields.Float(string="Quantity6")

    barcode7 = fields.Char(string="Barcode7",help="LDM/Combo Barcode[0-10]",index=True)
    quantity7 = fields.Float(string="Quantity7")

    barcode8 = fields.Char(string="Barcode8",help="LDM/Combo Barcode[0-10]",index=True)
    quantity8 = fields.Float(string="Quantity8")

    barcode9 = fields.Char(string="Barcode9",help="LDM/Combo Barcode[0-10]",index=True)
    quantity9 = fields.Float(string="Quantity9")

    barcode10 = fields.Char(string="Barcode10",help="LDM/Combo Barcode[0-10]",index=True)
    quantity10 = fields.Float(string="Quantity10")



    barcodes = fields.Char(string="Barcodes (ML)",help="Barcodes de la publicacione en ML",index=True)
    skus = fields.Char(string="Skus",index=True)
    stock = fields.Float(string="Stock",index=True)
    meli_id = fields.Char(string="Meli Id", index=True)
    meli_id_variation = fields.Char(string="Meli Id Variation", index=True)

    is_valid = fields.Boolean(string="Validez",default=False,index=True)

    def calculate_variations( self, meli=None ):
        account = None
        meli = meli
        for p in self:
            p.meli_id_variations = None
            p.meli_id_variations_number = 0
            meli_id = p.meli_id
            if ( not ( account == p.connection_account )):
                account = p.connection_account
                meli = None
                if not meli:
                    company = account.company_id or account.env.user.company_id
                    ac_official_store_id = account.official_store_id
                    seller_id = account.seller_id
                    meli = self.env['meli.util'].get_new_instance( company, account )

            rjson = account.fetch_meli_product( meli_id = meli_id, meli=meli )
            p.meli_id_variations = (rjson and "variation_ids" in rjson and rjson["variation_ids"]) or '[]'
            p.meli_id_variations_number = (rjson and "variations" in rjson and len(rjson["variations"])) or 0.0
            p.barcodes = (rjson and "barcodes" in rjson and rjson["barcodes"]!='[]' and rjson["barcodes"]) or (rjson and "barcode" in rjson and rjson["barcode"])
            p.skus = (rjson and "seller_skus" in rjson and rjson["seller_skus"])or (rjson and "seller_sku" in rjson and rjson["seller_sku"])
            #p.is_valid = (p.barcode and p.barcodes and p.barcode in p.barcodes)
            p.is_valid = True
            p.is_valid = p.is_valid and (p.sku and p.skus and p.sku in p.skus)
            _logger.info("is_valid:"+str(p.is_valid)+" sku <"+str(p.sku)+"> skus <"+str(p.skus)+">")
            p.status = ( (p.is_valid == False and 'invalid') or
                         (p.is_valid and p.is_master and not p.is_combo and 'master_base') or
                         (p.is_valid and p.is_master and p.is_combo and 'master_combo') or
                         (p.is_valid and not p.is_master and not p.is_combo and 'clone_base') or
                         (p.is_valid and not p.is_master and p.is_combo and 'clone_combo') )
            p.is_sku_odoo = p.sku and self.env["product.product"].search([('default_code','=ilike',p.sku)],limit=1)
            p.is_barcode_odoo = p.barcode and self.env["product.product"].search([('barcode','=ilike',p.barcode)],limit=1)
            is_combo_valid = p.is_combo
            #Ya no pedimos el barcode para combos... solo sku... and p.barcode
            #ningun componente tiene el mismo barcode que el producto
            is_combo_valid = is_combo_valid and (p.barcode0 and p.barcode0 != p.barcode and p.quantity0>0 or not p.barcode0)
            is_combo_valid = is_combo_valid and (p.barcode1 and p.barcode1 != p.barcode and p.quantity1>0 or not p.barcode1)
            is_combo_valid = is_combo_valid and (p.barcode2 and p.barcode2 != p.barcode and p.quantity2>0 or not p.barcode2)
            is_combo_valid = is_combo_valid and (p.barcode3 and p.barcode3 != p.barcode and p.quantity3>0 or not p.barcode3)
            is_combo_valid = is_combo_valid and (p.barcode4 and p.barcode4 != p.barcode and p.quantity4>0 or not p.barcode4)
            is_combo_valid = is_combo_valid and (p.barcode5 and p.barcode5 != p.barcode and p.quantity5>0 or not p.barcode5)
            is_combo_valid = is_combo_valid and (p.barcode6 and p.barcode6 != p.barcode and p.quantity6>0 or not p.barcode6)
            is_combo_valid = is_combo_valid and (p.barcode7 and p.barcode7 != p.barcode and p.quantity7>0 or not p.barcode7)
            is_combo_valid = is_combo_valid and (p.barcode8 and p.barcode8 != p.barcode and p.quantity8>0 or not p.barcode8)
            is_combo_valid = is_combo_valid and (p.barcode9 and p.barcode9 != p.barcode and p.quantity9>0 or not p.barcode9)
            is_combo_valid = is_combo_valid and (p.barcode10 and p.barcode10 != p.barcode and p.quantity10>0 or not p.barcode10)
            is_combo_valid = is_combo_valid or not p.is_combo

            p.is_valid = p.is_valid and is_combo_valid
            #lista de materiales
            p.is_barcode0_odoo = p.barcode0 and self.env["product.product"].search([('barcode','=ilike',p.barcode0)],limit=1)
            p.is_barcode1_odoo = p.barcode1 and self.env["product.product"].search([('barcode','=ilike',p.barcode1)],limit=1)
            p.is_barcode2_odoo = p.barcode2 and self.env["product.product"].search([('barcode','=ilike',p.barcode2)],limit=1)
            p.is_barcode3_odoo = p.barcode3 and self.env["product.product"].search([('barcode','=ilike',p.barcode3)],limit=1)
            p.is_barcode4_odoo = p.barcode4 and self.env["product.product"].search([('barcode','=ilike',p.barcode4)],limit=1)
            p.is_barcode5_odoo = p.barcode5 and self.env["product.product"].search([('barcode','=ilike',p.barcode5)],limit=1)
            p.is_barcode6_odoo = p.barcode6 and self.env["product.product"].search([('barcode','=ilike',p.barcode6)],limit=1)
            p.is_barcode7_odoo = p.barcode7 and self.env["product.product"].search([('barcode','=ilike',p.barcode7)],limit=1)
            p.is_barcode8_odoo = p.barcode8 and self.env["product.product"].search([('barcode','=ilike',p.barcode8)],limit=1)
            p.is_barcode9_odoo = p.barcode9 and self.env["product.product"].search([('barcode','=ilike',p.barcode9)],limit=1)
            p.is_barcode10_odoo = p.barcode10 and self.env["product.product"].search([('barcode','=ilike',p.barcode10)],limit=1)


        for p in self:
            p.is_it_master()
            p._is_bom_created()
            p._is_bom_valid()

    status = fields.Selection( [('invalid','Invalido'),
                                    ('master_base','Maestro Base'),
                                    ('master_combo','Maestro Combo'),
                                    ('clone_base','Clone Base'),
                                    ('clone_combo','Clone Combo')],
                                    string="Status",
                                    default='invalid',
                                    compute=calculate_variations,
                                    )

    def is_it_master( self ):
        for p in self:
            p.is_master = False;
            pobj = self.env["mercadolibre.product.maestro"]
            if p.barcode:
                #first: no combos
                pbases = pobj.search([('barcode','=',p.barcode),('is_combo','=',False)])
                if pbases:
                    max = 0
                    pbmax = None
                    for pb in pbases:
                        pbmax = (not pbmax and pb) or pbmax
                        #selecciona como master la publicacion con mas combinaciones de variantes en ML
                        if (pb.meli_id_variations_number>max):
                            max = pb.meli_id_variations_number
                            pbmax = pb
                        pb.is_master = False

                    #siempre que tenga SKUS y BARCODES para cada variante:
                    pbmax.is_master = True

                #second: combos
                pbasecombs = pobj.search([('barcode','like',p.barcode),('is_combo','=',True)])
                if pbasecombs:
                    max = 0
                    pbmax = None
                    for pb in pbasecombs:
                        pbmax = (not pbmax and pb) or pbmax
                        #selecciona como master la publicacion con mas combinaciones de variantes en ML
                        if (pb.meli_id_variations_number>max):
                            max = pb.meli_id_variations_number
                            pbmax = pb
                        pb.is_master = False

                    #siempre que tenga SKUS y BARCODES para cada variante:
                    pbmax.is_master = True
            elif p.sku:
                #first: no combos
                pbases = pobj.search([('sku','=',p.sku),('is_combo','=',False)])
                if pbases:
                    max = 0
                    pbmax = None
                    for pb in pbases:
                        pbmax = (not pbmax and pb) or pbmax
                        #selecciona como master la publicacion con mas combinaciones de variantes en ML
                        if (pb.meli_id_variations_number>max):
                            max = pb.meli_id_variations_number
                            pbmax = pb
                        pb.is_master = False


                    #siempre que tenga SKUS y BARCODES para cada variante:
                    pbmax.is_master = True

            p._is_sku_valid()

            if not p.barcode and p.is_combo and p.sku and p.is_sku_valid and p.barcodes and p.is_combo_valid:
                #no necesita barcode este combo?
                #si tiene barcodes definidos en ML al menos tendremos una LM valido
                #revisar si hay un combo maestro con la misma lista de materiales exacta

                #POR AHORA LO CREAMOS
                pbasecombs = pobj.search([('sku','=ilike',p.sku),('is_combo','=',True)])
                if pbasecombs:
                    max = 0
                    pbmax = None
                    for pb in pbasecombs:
                        pbmax = (not pbmax and pb) or pbmax
                        #selecciona como master la publicacion con mas combinaciones de variantes en ML
                        if (pb.meli_id_variations_number>max):
                            max = pb.meli_id_variations_number
                            pbmax = pb
                        pb.is_master = False
                    #
                    pbmax.is_master = True


            p._is_sku_valid()

    meli_id_variations = fields.Char(string="Variations", compute=calculate_variations, store=True, index=True)
    meli_id_variations_number = fields.Float(string="Number", compute=calculate_variations, store=True, default=0)

    is_combo = fields.Boolean(string="Combo/Kit",index=True)
    is_combo_valid = fields.Boolean(string="Combo Valido",help="El barcode del producto/publicacion no puede ser un componente, o sea existir en uno de los barcode[0-10] ",index=True)
    is_master = fields.Boolean(string="Master",index=True)

    def _is_sku_valid(self):
        for pm in self:
            pm.is_sku_valid = False
            pm.is_barcode_valid = False
            pm.is_sku_valid = pm.sku and pm.skus and pm.sku in pm.skus
            pm.is_barcode_valid = pm.barcode and pm.barcodes and pm.barcode in pm.barcodes

    is_sku_valid = fields.Boolean(string="Sku valido",help="El sku coincide con alguna publicacion",index=True)
    is_barcode_valid = fields.Boolean(string="Barcode valido",help="El barcode coincide con alguna publicacion",index=True)

    is_sku_odoo = fields.Boolean(string="Is Sku Odoo",index=True)
    is_barcode_odoo = fields.Boolean(string="Is Barcode Odoo",index=True)
    is_meli_odoo = fields.Boolean(string="Is Meli Id in Odoo",index=True)

    is_barcode0_odoo = fields.Boolean(string="Is Barcode0 Odoo",default=False,index=True)
    is_barcode1_odoo = fields.Boolean(string="Is Barcode1 Odoo",default=False,index=True)
    is_barcode2_odoo = fields.Boolean(string="Is Barcode2 Odoo",default=False,index=True)
    is_barcode3_odoo = fields.Boolean(string="Is Barcode3 Odoo",default=False,index=True)
    is_barcode4_odoo = fields.Boolean(string="Is Barcode4 Odoo",default=False,index=True)
    is_barcode5_odoo = fields.Boolean(string="Is Barcode5 Odoo",default=False,index=True)
    is_barcode6_odoo = fields.Boolean(string="Is Barcode6 Odoo",default=False,index=True)
    is_barcode7_odoo = fields.Boolean(string="Is Barcode7 Odoo",default=False,index=True)
    is_barcode8_odoo = fields.Boolean(string="Is Barcode8 Odoo",default=False,index=True)
    is_barcode9_odoo = fields.Boolean(string="Is Barcode9 Odoo",default=False,index=True)
    is_barcode10_odoo = fields.Boolean(string="Is Barcode10 Odoo",default=False,index=True)


    #@api.model
    #def write(self, vals):
    #    Maestro = self
    #    ret = None
    #    if (Maestro):
    #        ret = Maestro.write(vals)
    #        Maestro.calculate_variations()
    #    return ret

    @api.model
    def create(self, vals):
        Maestro = super(MercadoLibreMaestro, self).create(vals)
        if (Maestro):
            Maestro.calculate_variations()
        return Maestro

    def _is_bom_created(self):

        bom = self.env["mrp.bom"]
        bom_l = self.env["mrp.bom.line"]

        for mas in self:

            mas.is_bom_created = False

            product_id = mas.barcode and self.env["product.product"].search([('barcode','=ilike',mas.barcode),('company_id','=',mas.company_id.id)])

            if not product_id:
                _logger.info("barcode not founded for base product, search sku")
                product_id = mas.sku and self.env["product.product"].search([('default_code','=ilike',mas.sku),('company_id','=',mas.company_id.id)])

            if (not product_id):
                _logger.info("default_code or barcode not founded for base product")
                continue;

            if (not mas.is_combo):
                continue;

            bom_obj = bom.search([('product_tmpl_id','=',product_id.product_tmpl_id.id),('product_id','=',product_id.id)])

            if not bom_obj:
                continue;

            mas.is_bom_created = True


    is_bom_created = fields.Boolean(string="Is LDM/Bom Created",compute=_is_bom_created,default=False,store=True,index=True)

    def _is_bom_valid(self):

        bom = self.env["mrp.bom"]
        bom_l = self.env["mrp.bom.line"]

        for mas in self:

            mas.is_bom_valid = False

            product_id = mas.barcode and self.env["product.product"].search([('barcode','=ilike',mas.barcode),('company_id','=',mas.company_id.id)])

            if not product_id:
                _logger.info("barcode not founded for base product, search sku")
                product_id = mas.sku and self.env["product.product"].search([('default_code','=ilike',mas.sku),('company_id','=',mas.company_id.id)])

            if (not product_id):
                _logger.info("default_code or barcode not founded for base product")
                continue;

            if (not mas.is_combo):
                continue;

            bom_obj = bom.search([('product_tmpl_id','=',product_id.product_tmpl_id.id),('product_id','=',product_id.id)])

            if not bom_obj:
                continue;

            #search for same product target bom as component product
            bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_id.id)])

            if bom_obj_l:
                mas.is_bom_valid = False
                continue;

            mas.is_bom_valid = True

    is_bom_valid = fields.Boolean(string="Is LDM/Bom Valid",compute=_is_bom_valid,default=False,store=True,index=True)

    def _product_by_sku(self):
        for mas in self:
            mas.product_by_sku = None
            mas.product_by_sku = self.env["product.product"].search([('default_code','=ilike', mas.sku)], limit=1)

    product_by_sku = fields.Many2one("product.product",string="Product por Sku",compute=_product_by_sku)
    product_template_by_sku = fields.Many2one("product.template",string="Product template por Sku",related="product_by_sku.product_tmpl_id")

    def create_bom( self, product_id=None ):

        bom = self.env["mrp.bom"]
        bom_l = self.env["mrp.bom.line"]

        for mas in self:
            if (product_id==None):
                product_id = mas.barcode and self.env["product.product"].search([('barcode','=ilike',mas.barcode),('company_id','=',mas.company_id.id)])
                if not product_id:
                    _logger.info("barcode not founded for base product, search sku")
                    product_id = mas.sku and self.env["product.product"].search([('default_code','=ilike',mas.sku),('company_id','=',mas.company_id.id)])

            if (not product_id):
                _logger.info("default_code or barcode not founded for base product")
                continue;

            if (not mas.is_combo):
                continue;

            uomobj = self.env[uom_model]
            uomcatobj = self.env["uom.category"]
            product_uom_id = uomobj.search([('name','=ilike','Uni%')],limit=1)
            product_uom_category_id = uomcatobj.search([('name','=ilike','Uni%')],limit=1)
            if not product_uom_id:
                _logger.info("no product_uom_id")
                continue;
            if not product_uom_category_id:
                _logger.info("no product_uom_category_id")
                continue;

            bom_rec =  {
                'product_tmpl_id': product_id.product_tmpl_id.id,
                'product_id': product_id.id,
                "type": "phantom",
                "product_qty": 1,
                "product_uom_id": product_uom_id.id,
                "product_uom_category_id": product_uom_category_id.id
            }
            _logger.info("sku: "+str(mas.sku))
            _logger.info("barcode: "+str(mas.barcode))
            _logger.info("bom_rec: "+str(bom_rec))
            bom_obj = bom.search([('product_tmpl_id','=',product_id.product_tmpl_id.id),('product_id','=',product_id.id)])
            if not bom_obj:
                bom_obj = bom.create(bom_rec)

            if not bom_obj:
                continue;


            if (mas.barcode0 and mas.quantity0>0):

                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode0)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode0))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity0
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )
                else:
                    _logger.info("Not found! "+str(mas.barcode0))

            if (mas.barcode1 and mas.quantity1>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode1)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode1))
                        continue;

                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity1
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )
                else:
                    _logger.info("Not found! "+str(mas.barcode1))

            if (mas.barcode2 and mas.quantity2>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode2)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode2))
                        continue;

                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity2
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )
                else:
                    _logger.info("Not found! "+str(mas.barcode2))

            if (mas.barcode3 and mas.quantity3>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode3)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode3))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity3
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )
                else:
                    _logger.info("Not found! "+str(mas.barcode3))

            if (mas.barcode4 and mas.quantity4>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode4)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode4))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity4
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )

            if (mas.barcode5 and mas.quantity5>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode5)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode5))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity5
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )


            if (mas.barcode6 and mas.quantity6>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode6)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode6))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity6
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )



            if (mas.barcode7 and mas.quantity7>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode7)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode7))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity7
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )


            if (mas.barcode8 and mas.quantity8>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode8)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode8))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity8
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )


            if (mas.barcode9 and mas.quantity9>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode9)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode9))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity9
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )


            if (mas.barcode10 and mas.quantity10>0):
                product_bom_id = product_id.search([('barcode','=ilike',mas.barcode10)])
                if product_bom_id:
                    if (product_bom_id.id==product_id.id):
                        _logger.info("Error! component is also the product! "+str(mas.barcode10))
                        continue;
                    bom_obj_l = bom_l.search([('bom_id','=',bom_obj.id),('product_id','=',product_bom_id.id)])

                    bomline_fields = {
                        'bom_id': bom_obj.id,
                        'product_id': product_bom_id.id,
                        'product_uom_id': product_uom_id.id,
                        'product_qty': mas.quantity10
                    }
                    if (bom_obj_l):
                        bom_obj_l.write(bomline_fields)
                    else:
                        bom_l.create( bomline_fields )

        self._is_bom_created()
        self._is_bom_valid()

class MercadoLibreConnectionAccount(models.Model):

    _name = "mercadolibre.account"
    _description = "MercadoLibre Account"
    _inherit = "ocapi.connection.account"

    configuration = fields.Many2one( "mercadolibre.configuration", string="Connection Parameters Configuration", help="Connection Parameters Configuration", required=True  )
    #type = fields.Selection([("custom","Custom"),("mercadolibre","MercadoLibre")],string='Connector',index=True)
    type = fields.Selection(selection_add=[("mercadolibre","MercadoLibre")],
				string='Connector Type',
				default="mercadolibre",
				ondelete={'mercadolibre': 'set default'},
				index=True,
				required=True)
    country_id = fields.Many2one("res.country",string="Country",index=True, required=True)

    refresh_token = fields.Char(string='Refresh Token', help='Refresh Token',size=128)
    meli_login_id = fields.Char( string="Meli Login Id", help="https://compania.odoo.com/meli_login/{Meli Login Id}  Por ejemplo, si el Redirect Uri es: https://compania.odoo.com/meli_login/micanaluno el Meli Login Id es: micanaluno", index=True, required=True)
    redirect_uri = fields.Char( string='Redirect Uri', help='Redirect uri (https://myodoodomain.com/meli_login/[meli_login_id])',size=1024, index=True, required=True)
    cron_refresh = fields.Boolean(string="Cron Refresh", index=True)
    code = fields.Char( string="Code", index=True)
    official_store_id = fields.Char(string="Official Store Id",related="configuration.mercadolibre_official_store_id")

    maestro_products = fields.One2many("mercadolibre.product.maestro","connection_account",string="Productos maestros")

    def _mercadolibre_brands( self ):
        brands = []
        for ac in self:
            company = ac.company_id or ac.env.user.company_id
            ac_official_store_id = ac.official_store_id
            seller_id = ac.seller_id
            meli = self.env['meli.util'].get_new_instance( company, ac )
            #ac.mercadolibre_brands = [(5)]
            if meli:
                response = meli.get("/users/"+str(seller_id)+"/brands", {'access_token':meli.access_token })
                rjson = response and response.json()
                #_logger.info("_mercadolibre_brands rjson: "+str(rjson))
                if rjson and not "error" in rjson and "brands" in rjson:
                    #search and create
                    for bra in rjson["brands"]:
                        #_logger.info("_mercadolibre_brands bra: "+str(bra))

                        brand = {
                            "name": "name" in bra and bra["name"],
                            "site_id": "site_id" in bra and bra["site_id"],
                            "official_store_id": "official_store_id" in bra and bra["official_store_id"],
                            "seller_id": seller_id,

                            "fantasy_name": "fantasy_name" in bra and bra["fantasy_name"],
                            "status": "status" in bra and bra["status"],
                            "type": "type" in bra and bra["type"],
                            "permalink": "permalink" in bra and bra["permalink"],
                        }

                        official_store_id = 'official_store_id' in bra and bra['official_store_id']
                        br = self.env["mercadolibre.brand"].search([('official_store_id','=',str(official_store_id) )])
                        if not br or not br.id:
                            #skip

                            br = self.env["mercadolibre.brand"].create(brand)
                            #if br:
                            #    _logger.info("Created mercadolibre.brand: "+str(brand)+" id:"+str(br))
                        else:
                            br.write(brand)

                        brands.append(br)


        return brands
                        #    ac.mercadolibre_brands = [(4,0,[br.id])]

    #mercadolibre_brands = fields.Many2many("mercadolibre.brand",relation='mercadolibre_account_brands_rel',string="Brands")


    def _meli_brand( self ):
        for ac in self:
            ac.brand = None
            #if not ac.mercadolibre_brands:
            mercadolibre_brands = ac._mercadolibre_brands()
            _logger.info("mercadolibre_brands: "+str(mercadolibre_brands))
            if mercadolibre_brands:
                for br in mercadolibre_brands:
                    if br.official_store_id and str(br.official_store_id)==str(ac.official_store_id):
                        ac.brand = br

    brand = fields.Many2one("mercadolibre.brand",compute=_meli_brand,string="Brand" )

    def create_credentials(self, context=None):
        context = context or self.env.context
        _logger.info("create_credentials: " + str(context))

        now = datetime.now()
        date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
        base_str = str(self.name) + str(date_time)

        hash = hashlib.md5(base_str.encode())
        hexhash = hash.hexdigest()

        self.client_id = hexhash

        base_str = str(self.name) +str(self.client_id) + str(date_time)

        hash = hashlib.md5(base_str.encode())
        hexhash = hash.hexdigest()

        self.secret_key = hexhash

    def authorize_token(self, client_id, secret_key ):

        if not secret_key or not client_id or self.client_id != client_id or self.secret_key != secret_key:
            return { "error": "Bad credentials", "message": "Bad credentials, values does not match with any configuration" }

        now = datetime.now()
        date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
        base_str = str(client_id) + str(secret_key) + str(date_time)

        hash = hashlib.blake2b()
        hash.update( base_str.encode() )
        hexhash = hash.hexdigest()

        access_token = hexhash
        self.access_token = access_token

        return access_token

    def get_connector_state(self):

        for connacc in self:
            connacc.status = "disconnected"
            _logger.info( 'meli_oerp_multiple account get_connector_state() ' + str(connacc and connacc.name) )
            meli = self.env['meli.util'].get_new_instance( connacc.company_id, connacc )
            if meli:
                if meli.needlogin_state:
                    connacc.status = "disconnected"
                else:
                    connacc.status = "connected"

    status = fields.Selection([("disconnected","Disconnected"),("connected","Connected")],
                                string="Status",
                                compute='get_connector_state')
    state = fields.Boolean( compute='get_connector_state', string="State", help="Estado de la conexión", readonly=False )

    mercadolibre_product_template_bindings = fields.One2many( "mercadolibre.product_template", "connection_account", string="Product Bindings" )
    mercadolibre_product_bindings = fields.One2many( "mercadolibre.product", "connection_account", string="Product Variant Bindings" )
    mercadolibre_orders = fields.One2many( "mercadolibre.orders", "connection_account", string="Orders" )

    def meli_refresh_token(self):
        _logger.info("meli_refresh_token")
        self.ensure_one()
        company = self.company_id or self.env.user.company_id
        _logger.info(self.name)
        _logger.info(self.company_id.name)
        meli = self.env['meli.util'].get_new_instance( company, self )

        _logger.info("meli:"+str(meli))

    def meli_login(self):
        _logger.info("meli_login")
        _logger.info('company.meli_login() ')
        self.ensure_one()
        company = self.company_id or self.env.user.company_id
        _logger.info(self)
        _logger.info(self.company_id)
        meli = self.env['meli.util'].get_new_instance(company,self)

        return meli.redirect_login()

    def meli_logout(self):
        _logger.info("meli_logout")
        self.ensure_one()
        company = (self and self.company_id) or self.env.user.company_id
        self.status = "disconnected"
        #self.state = True
        company.write({'mercadolibre_access_token': '', 'mercadolibre_refresh_token': '', 'mercadolibre_code': '' } )
        self.write({'access_token': '', 'refresh_token': '', 'code': '' } )
        return ""

    def meli_notifications(self, data=False, meli=None):

        account = self
        company = (account and account.company_id) or self.env.user.company_id
        config = (account and account.configuration) or company

        _logger.info("account >> meli_notifications "+str(account.name))

        if (config.mercadolibre_process_notifications):
            return self.env['mercadolibre.notification'].fetch_lasts( data=data, company=company, account=account, meli=meli )
        return {}

#MELI CRON

    def cron_meli_process_internal_jobs(self):
        _logger.info('account cron_meli_process_internal_jobs() ')
        for connacc in self:

            company = connacc.company_id or self.env.user.company_id
            config = connacc.configuration or company

            apistate = self.env['meli.util'].get_new_instance( company, connacc)
            if apistate.needlogin_state:
                return True

            if (config.mercadolibre_cron_post_update_stock):
                _logger.info("config.mercadolibre_cron_post_update_stock True "+str(config.name))
                connacc.meli_update_remote_stock_injobs( meli=apistate )


    def cron_meli_orders(self):
        _logger.info('account cron_meli_orders() ')

        for connacc in self:
            company = connacc.company_id or self.env.user.company_id
            config = (connacc and connacc.configuration) or company

            apistate = self.env['meli.util'].get_new_instance( company, connacc)
            if apistate.needlogin_state:
                return True

            if (config.mercadolibre_cron_get_orders):
                _logger.info("account config mercadolibre_cron_get_orders")
                connacc.meli_query_orders()

            #if (config.mercadolibre_cron_get_questions):
            #    _logger.info("account config mercadolibre_cron_get_questions")
            #    connacc.meli_query_get_questions()


    def cron_meli_process( self ):

        #_logger.info( 'account cron_meli_process() STARTED ' + str( datetime.now() ) )

        for connacc in self:

            company = connacc.company_id or self.env.user.company_id
            config = connacc.configuration or company

            apistate = self.env['meli.util'].get_new_instance( company, connacc)
            if apistate.needlogin_state:
                return True

            if (config.mercadolibre_cron_get_update_products):
                _logger.info("config.mercadolibre_cron_get_update_products")
                connacc.meli_update_local_products()

            if (config.mercadolibre_cron_get_new_products):
                _logger.info("config.mercadolibre_cron_get_new_products")
                connacc.product_meli_get_products()

            if (config.mercadolibre_cron_post_update_products or config.mercadolibre_cron_post_new_products):
                _logger.info("config.mercadolibre_cron_post_update_products")
                connacc.meli_update_remote_products(post_new=connacc.configuration.mercadolibre_cron_post_new_products)

            if (config.mercadolibre_cron_post_update_stock):
                _logger.info("config.mercadolibre_cron_post_update_stock")
                connacc.meli_update_remote_stock(meli=apistate)

            if (config.mercadolibre_cron_post_update_price):
                _logger.info("config.mercadolibre_cron_post_update_price")
                connacc.meli_update_remote_price(meli=apistate)


        #_logger.info( 'account cron_meli_process() ENDED ' + str( datetime.now() ) )
    #TODO: {
    #  "id": "GTIN",
    #  "name": "Código universal de producto",
    #  "value_id": null,
    #  "value_name": "758475398510",
    #  "value_struct": null,
    #  "values": []
    #}
    #{
    #  "id": "SELLER_SKU",
    #  "name": "SKU",
    #  "value_id": null,
    #  "value_name": "ELEF60_ROSA",
    #  "value_struct": null,
    #  "values": []
    #}
    def fetch_meli_product( self, meli_id, meli=None ):

        rjson = {}
        account = self
        seller_sku = None

        _logger.info("Fetch Meli Product: "+str(meli_id)+" account: "+str(account))

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        if not meli_id or not meli:
            return None

        #search full item data from ML
        #import pdb;pdb.set_trace()
        response = meli.get("/items/"+meli_id, {'access_token':meli.access_token, 'include_attributes': 'all' })
        rjson = response.json()

        #single item SKU
        if rjson and "attributes" in rjson:
            for att in rjson['attributes']:
                if ("id" in att and att["id"] == "SELLER_SKU"):
                    seller_sku = att["value_name"]
                    rjson['seller_sku'] = seller_sku
                if ("id" in att and att["id"] == "GTIN"):
                    rjson["barcode"] =  att["value_name"]

        if (not seller_sku and 'seller_custom_field' in rjson and rjson['seller_custom_field'] and len(rjson['seller_custom_field'])):
            seller_sku = rjson['seller_custom_field']
            rjson['seller_sku'] = seller_sku

        #we have description
        #if rjson and 'descriptions' in rjson and rjson['descriptions']:
        if rjson and 'descriptions' in rjson and not rjson['descriptions']:
            dresponse = meli.get("/items/"+str(meli_id)+"/description", {'access_token':meli.access_token })
            djson = dresponse.json()
            des = ""
            desplain = ""
            if 'text' in djson:
               des = djson['text']
            if 'plain_text' in djson:
               desplain = djson['plain_text']
            if (len(des)>0):
                desplain = des
            rjson["description"] = desplain

        #we have variants
        if "variations" in rjson and len(rjson["variations"]):
            vindex = -1
            rjson['seller_skus'] = '['
            rjson['barcodes'] = '['
            rjson['variation_ids'] = '['
            comai = ''
            comas = ''
            comab = ''
            for var in rjson['variations']:
                vindex = vindex+1
                vjson = rjson['variations'][vindex]
                meli_id_variation = ("id" in var and var["id"])
                #_logger.info(meli_id_variation)
                if meli_id_variation:
                    if not ("attributes" in vjson):
                        varget = "/items/"+str(meli_id)+"/variations/"+str(meli_id_variation)
                        #_logger.info("https://api.mercadolibre.com"+varget+"?access_token="+str(meli.access_token))
                        resvar = meli.get( varget, { 'access_token': meli.access_token } )
                        if ( "error" in resvar.json() ):
                            _logger.error(resvar.json())
                            #continue;
                        else:
                            vjson = resvar.json()
                            rjson['variations'][vindex] = vjson

                    if "attributes" in vjson:
                        for att in vjson["attributes"]:
                            if ("id" in att and att["id"] == "SELLER_SKU"):
                                rjson['variations'][vindex]["seller_sku"] = att["value_name"]
                                rjson['seller_skus']+= comas+str(att["value_name"])
                                comas = ','
                                if (len(rjson["variations"])==1):
                                    rjson['seller_sku'] = att["value_name"]


                            if ("id" in att and att["id"] == "GTIN"):
                                rjson['variations'][vindex]["barcode"] = att["value_name"]
                                rjson['barcodes']+= comab+str(att["value_name"])
                                comab = ','

                    rjson['variation_ids']+= comai+str(meli_id_variation)
                    comai = ','

            rjson['seller_skus']+= ']'
            rjson['barcodes']+= ']'
            rjson['variation_ids']+= ']'

        #_logger.info("Fetch Meli Product, rjson: " +str(rjson))

        return rjson

    def fetch_meli_sku(self, meli_id = None, meli_id_variation = None, meli = None, rjson = None ):

        account = self
        seller_sku = None

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        if not meli_id or not meli:
            return None

        #search full item data from ML
        rjson = rjson or account.fetch_meli_product( meli_id = meli_id, meli=meli )
        rjson_has_variations = rjson and "variations" in rjson and len(rjson["variations"])

        if ( account.configuration.mercadolibre_import_search_sku ):

            #its a single product item with seller_custom_field defined or seller_sku
            seller_sku = ('seller_sku' in rjson and rjson['seller_sku']) or ('seller_custom_field' in rjson and rjson['seller_custom_field'])

            if (rjson_has_variations):
                vindex = -1
                seller_sku = []
                for var in rjson['variations']:
                    vindex = vindex+1
                    if not meli_id_variation:
                        #return all skus
                        if ("seller_sku" in var):
                            seller_sku.append(var["seller_sku"])

                    if meli_id_variation and "id" in var and str(var["id"]) == str(meli_id_variation):
                        #check match, return sku if founded
                        seller_sku = ('seller_sku' in var and var['seller_sku']) or ('seller_custom_field' in var and var['seller_custom_field'])
                        break;

        return seller_sku

    def fetch_meli_barcode(self, meli_id = None, meli_id_variation = None, meli = None, rjson = None ):

        account = self
        barcode = None

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        if not meli_id or not meli:
            return None

        #search full item data from ML
        rjson = rjson or account.fetch_meli_product( meli_id = meli_id, meli=meli )
        rjson_has_variations = rjson and "variations" in rjson and len(rjson["variations"])

        if ( account.configuration.mercadolibre_import_search_sku ):

            #its a single product item with seller_custom_field defined or seller_sku
            barcode = ('barcode' in rjson and rjson['barcode'])

            if (rjson_has_variations):
                vindex = -1
                v_barcode = []
                for var in rjson['variations']:
                    vindex = vindex+1
                    if not meli_id_variation:
                        #return all skus
                        if ("barcode" in var):
                            v_barcode.append(var["barcode"])

                    if meli_id_variation and "id" in var and str(var["id"]) == str(meli_id_variation):
                        #check match, return sku if founded
                        v_barcode = ('barcode' in var and var['barcode'])
                        break;

                barcode = v_barcode or barcode

        return barcode

    def set_meli_sku( self, seller_sku=None ):
        if (seller_sku):
            posting_id = self.env['product.product'].search([('default_code','=ilike',seller_sku)])
            if (not posting_id or len(posting_id)==0):
                posting_id = self.env['product.template'].search([('default_code','=ilike',seller_sku)])
                _logger.info("Founded template with default code, dont know how to handle it.")
            else:
                posting_id.meli_id = item_id

        #search variations in ml rjson item, and updates odoo product meli_id_variation if founded default_code
        #if ('variations' in rjson3):
        #    for var in rjson3['variations']:
        #        if ('seller_custom_field' in var and var['seller_custom_field'] and len(var['seller_custom_field'])):
        #            posting_id = self.env['product.product'].search([('default_code','=ilike',var['seller_custom_field'])])
        #            if (posting_id):
        #                posting_id.meli_id = item_id
        #                if (len(posting_id.product_tmpl_id.product_variant_ids)>1):
        #                    posting_id.meli_id_variation = var['id']

    def search_meli_product( self, meli_id = None, meli_id_variation = None, seller_sku=None, barcode=None, meli=None, rjson=None ):

        account = self
        old_posting_id = None #product search by model.meli_id
        sku_product_id = None #product search by sku
        barcode_product_id = None #product search by barcode
        ml_bind_product_id = None #product search by account binding and model.conn_id/conn_variation_id

        rjson = rjson or account.fetch_meli_product( meli_id = item_id, meli=meli )
        rjson_has_variations = rjson and "variations" in rjson and len(rjson["variations"])

        #old meli_oerp association
        old_posting_id = self.env['product.product'].search([('meli_id','=',meli_id)])
        #_logger.info("search_meli_product old_posting_id: "+str(old_posting_id))

        if old_posting_id:

            if len(old_posting_id)>1:
                _logger.info("Duplicates old associations, maybe variants #"+str(len(old_posting_id)))
                #check rjson for variations
                if rjson_has_variations:
                    for vjson in rjson["variations"]:
                        _logger.info(vjson)

            for old_prod in old_posting_id:
                _logger.info("Product in database, check his bindings: " + str(old_prod.display_name)+str(" #")+str(len(old_prod.mercadolibre_bindings)) )

                if old_prod.mercadolibre_bindings:
                    _logger.info("Has ML binding connections: " + str(old_posting_id.mercadolibre_bindings) )

                for bind in old_prod.mercadolibre_bindings:
                    _logger.info( bind.name )

        #new binding method
        ml_bind_product_id = account.search_meli_binding_product(meli_id = meli_id)
        if ml_bind_product_id:
            _logger.info("Binding Product Id found: "+str(ml_bind_product_id))
            #TODO: chequear si coinciden cantidad de variantes y revincular

        #No binding and no posting, or binding but no more product deep search
        if not ml_bind_product_id or (ml_bind_product_id and not ml_bind_product_id.product_id):
            _logger.info("Binding Product Id NOT FOUND or NOT SET: "+str(ml_bind_product_id))
            ml_bind_product_id = False
            if not old_posting_id:
                _logger.info("Deep search of the product! : fetch sku: ")
                seller_sku = seller_sku or self.fetch_meli_sku(meli_id=meli_id, meli_id_variation = meli_id_variation, meli=meli, rjson=rjson)
                if seller_sku:
                    _logger.info("seller_sku(s) fetched: "+str(seller_sku))
                    if type(seller_sku) in (tuple, list):
                        sku_product_ids = False
                        for sku in seller_sku:
                            _logger.info("seller_sku search: "+str(sku))
                            sku_product_id = self.env['product.product'].search([ ('default_code','=ilike',sku) ])
                            if sku_product_ids and sku_product_id:
                                sku_product_ids+= sku_product_id
                            elif sku_product_id:
                                sku_product_ids = sku_product_id
                        sku_product_id = sku_product_ids and sku_product_ids[0]
                    else:
                        sku_product_id = self.env['product.product'].search([ ('default_code','=ilike',seller_sku) ])
                    #sku_product_id = self.env['product.product'].search([ '|', ('default_code','=',seller_sku), ('barcode','=',seller_sku) ])

                        if sku_product_id and len(sku_product_id)>1:
                            #DUPLICATES SKUS ???
                            #take the first one and report the problem?
                            #sku_product_id = sku_product_id[0]
                            sku_product_id = None

                else:
                    _logger.info("NO seller_sku (warning!!!! must define a seller sku in ML, or activate mercadolibre_import_search_sku)")

                _logger.info("Deep search of the product! : fetch barcode: ")
                barcode = barcode or self.fetch_meli_barcode(meli_id=meli_id, meli_id_variation = meli_id_variation, meli=meli, rjson=rjson)
                if barcode:
                    _logger.info("barcode(s) fetched: ["+str(barcode)+"]")

                    if type(barcode) in (tuple, list):
                        barcode_product_ids = False
                        for bcode in barcode:
                            _logger.info("barcode search: ["+str(bcode)+"]")
                            barcode_product_id = self.env['product.product'].search([ ('barcode','=ilike',bcode) ])
                            _logger.info("barcode found: "+str(barcode_product_id))
                            if barcode_product_ids and barcode_product_id:
                                barcode_product_ids+= barcode_product_id
                            elif barcode_product_id:
                                barcode_product_ids = barcode_product_id
                        barcode_product_id = barcode_product_ids and barcode_product_ids[0]
                    else:
                        _logger.info("barcode search: ["+str(barcode)+"]")
                        barcode_product_id = self.env['product.product'].search([ ('barcode','=ilike',barcode) ])
                    #sku_product_id = self.env['product.product'].search([ '|', ('default_code','=',seller_sku), ('barcode','=',seller_sku) ])

                        if barcode_product_id and len(barcode_product_id)>1:
                            #DUPLICATES SKUS ???
                            #take the first one and report the problem?
                            #sku_product_id = sku_product_id[0]
                            barcode_product_id = None

                    _logger.info("barcode(s) fetched: barcode_product_id: "+str(barcode_product_id))

                else:
                    _logger.info("NO barcode (warning!!!! must define a seller barcode in ML, or activate mercadolibre_import_search_sku)")

            else:
                #bind! update bind!
                #old_posting_id.mercadolibre_bind_to( account, )
                _logger.info("Product need binding: "+str(old_posting_id[0].product_tmpl_id.display_name))

        #new_posting_tpl_id = self.env['mercadolibre.product_template'].search([('conn_id','=',meli_id)]) #('conn_variation_id','=','meli_id_variation'
        #_logger.info("new_posting_tpl_id: "+str(new_posting_tpl_id))

        #prioritize binding (so we do not duplicate article nor binded)
        product_id = (ml_bind_product_id and ml_bind_product_id.product_id) or old_posting_id or sku_product_id or barcode_product_id

        _logger.info("search result: product_id, ml_bind_product_id: "+str(product_id)+", "+str(ml_bind_product_id))

        return product_id, ml_bind_product_id

    def search_meli_binding_product( self, meli_id = None, meli_id_variation=None ):
        account = self
        #new
        ml_bind_product_id = self.env['mercadolibre.product'].search([('conn_id','=',meli_id),
                                                                      #('conn_variation_id','=',meli_id_variation),
                                                                      ("connection_account","=",account.id)])
        if meli_id_variation:
            ml_bind_product_id_var = self.env['mercadolibre.product'].search([('conn_id','=',meli_id),
                                                                      ('conn_variation_id','=',meli_id_variation),
                                                                      ("connection_account","=",account.id)])
            ml_bind_product_id = ml_bind_product_id_var

        if ml_bind_product_id:
            _logger.info("Binding Product Id: "+str(ml_bind_product_id))
        else:
            _logger.info("NO Binding variant, search for template binding")
            ml_bind_product_template_id = self.env['mercadolibre.product_template'].search([('conn_id','=',meli_id),("connection_account","=",account.id)]) #('conn_variation_id','=','meli_id_variation'
            if ml_bind_product_template_id:
                _logger.info("binding template found")
            else:
                _logger.info("NO Binding at all for this account.")

        #new_posting_tpl_id = self.env['mercadolibre.product_template'].search([('conn_id','=',meli_id)]) #('conn_variation_id','=','meli_id_variation'
        #_logger.info("new_posting_tpl_id: "+str(new_posting_tpl_id))


        return ml_bind_product_id

    def create_meli_product_boms( self, meli_id, product_template ):



        return True

    #create missing product
    def create_meli_product( self, meli_id = None, meli=None, rjson=None ):

        account = self
        seller_sku = None
        productcreated = None

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        if not meli_id or not meli:
            return None

        #search full item data from ML
        #response = meli.get("/items/"+meli_id, {'access_token':meli.access_token})
        rjson = rjson or account.fetch_meli_product(meli_id=meli_id,meli=meli)

        if "id" in rjson and str(rjson["id"])==str(meli_id):
            meli_title = rjson['title']
            prod_fields = {
                'name': meli_title.encode("utf-8"),
                'description': meli_title.encode("utf-8"),
                'meli_id': meli_id,
                'meli_pub': True,
            }
            prod_fields.update(ProductType())
            #prod_fields['default_code'] = rjson3['id']
            productcreated = self.env['product.product'].create((prod_fields))
            if (productcreated):
                product_template = productcreated.product_tmpl_id
                if (product_template):
                    product_template.meli_pub = True
                _logger.info( "Product created: " + str(productcreated) + " >> meli_id:" + str(meli_id) + "-" + str( meli_title.encode("utf-8")) )
                #pdb.set_trace()

                _logger.info(productcreated)
                result = productcreated.product_meli_get_product( meli_id=meli_id, account=account, meli=meli, rjson=rjson )
                if result and "error" in result:
                    _logger.error("ERROR Creating Odoo product from Meli product: "+str(result))
                    return productcreated
                if (product_template):
                    bindT = product_template.mercadolibre_bind_to( account=account, meli_id=meli_id, bind_variants=True, meli=meli, rjson=rjson )
                    if bindT:
                        # from_meli_oerp = True copy form recent imported
                        bindT.fetch_meli_product( meli=meli, from_meli_oerp=True, fetch_variants=True )
            else:
                _logger.error( "ERROR Creating Odoo product: "+str(prod_fields))
        else:
            _logger.error( "ERROR: Meli product not fetched: " + str(rjson) )

        return productcreated

#MELI


    def meli_query_orders(self):
        _logger.info("account >> meli_query_orders")
        account = self
        company = account.company_id or self.env.user.company_id

        orders_obj = self.env['mercadolibre.sale_order']
        result = orders_obj.orders_query_recent( account=account )
        return result

    def meli_query_get_questions(self):

        _logger.info("account >> meli_query_get_questions")
        for account in self:
            company = account.company_id or self.env.user.company_id
            config = account.configuration

            _logger.info("account >> meli_query_get_questions >> "+str(account.name))

            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                return meli.redirect_login()

            productT_bind_ids = self.env['mercadolibre.product_template'].search([
                ('connection_account', '=', account.id ),
            ], order='id asc')

            _logger.info("productT_bind_ids:"+str(productT_bind_ids))

            if productT_bind_ids:
                for bindT in productT_bind_ids:
                    _logger.info("account >> meli_query_get_questions >> "+str(bindT.name))
                    bindT.query_questions( meli=meli, config=config )


        return {}

    def meli_query_products(self):
        _logger.info("meli_query_products")
        #same as always...
        #iterate over products
        #bind if account not binded and product found with SKU or BINDING... remember to associate connector id (ml id)
        self.product_meli_get_products()

    def meli_update_local_products(self):
        _logger.info("meli_update_local_products")
        _logger.info(self)
        for account in self:
            account.product_meli_update_local_products()

    def meli_import_categories(self):
        _logger.info("meli_import_categories")


    def meli_pause_all(self):
        _logger.info("meli_pause_all")


#MELI internal

    def product_meli_update_local_products( self, meli=None ):

        account = self
        _logger.info('account.product_meli_update_local_products() '+str(account.name))
        company = account.company_id or self.env.user.company_id
        product_obj = self.env['product.product']

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                url_login_meli = meli.auth_url()

        #product_ids = self.env['product.product'].search([('meli_id','!=',False),
        #                                                  '|',('company_id','=',False),('company_id','=',company.id)])

        #product_ids = self.env['product.template'].search([
        #    ('meli_pub','!=',False),
        #    ('mercadolibre_bindings','!=',False),
        #    ('default_code','=',False)
        #    ] )

        product_ids = self.env['mercadolibre.product_template'].search([
            #('meli_pub','!=',False),
            #('mercadolibre_bindings','!=',False),
            ('product_tmpl_id','!=',False),
            ('sku', 'like', '%False%')
            ] )

        _logger.info(product_ids)

        if product_ids:
            cn = 0
            ct = len(product_ids)
            Autocommit(self)
            try:
                for obj in product_ids:
                    cn = cn + 1
                    _logger.info( "Product Bind Template to update: [" + str(obj.product_tmpl_id.display_name) + "] " + str(cn)+"/"+str(ct))
                    try:
                        #obj.product_meli_get_product()
                        obj.product_template_update()
                        self._cr.commit()
                    except Exception as e:
                        _logger.info("updating product > Exception error.")
                        _logger.error(e, exc_info=True)
                        pass;

            except Exception as e:
                _logger.info("product_meli_update_products > Exception error.")
                _logger.error(e, exc_info=True)
                self._cr.rollback()

        return {}


    def filter_meli_ids( self, results, store_id=None ):

        account = self

        company = account.company_id or self.env.user.company_id


        meli = self.env['meli.util'].get_new_instance( company, account )
        if meli.need_login():
            return meli.redirect_login()

        official_store_id = store_id
        if not official_store_id:
            return results

        c = 0
        n20 = 0
        rresults = []
        #_logger.info("results:"+str(results))
        if not results:
            return rresults

        ids = ""
        coma = ""
        maxc = (results and len(results)) or 0
        for meli_id in results:
            c+=1
            n20+=1

            #read id and official_store_id to check
            #hacer paquetes de 20 !!!!!! /items?ids=$ITEM_ID1,$ITEM_ID2&attributes=$ATTRIBUTE1,$ATTRIBUTE2,$ATTRIBUTE3

            #armamos el paquete
            ids+= coma+str(meli_id)
            coma = ","

            if n20==20 or c==maxc:
                item_params = {
                    "ids": str(ids),
                    "attributes": "id,official_store_id"
                }
                #_logger.info("item_params:"+str(item_params))
                responseItem = meli.get("/items"+str('?ids='+str(ids)+'&attributes='+str('id,official_store_id')), {} )
                #[ { "code": 200, "body": { "id": "MLM863472529", "official_store_id": 3476 } },
                #_logger.info("responseItem:"+str(responseItem and responseItem.json()))
                if responseItem.json():
                    for rr in responseItem.json():
                        #_logger.info("rr:"+str(rr))
                        if ("code" in rr and rr["code"]==200):
                            if ("body" in rr and rr["body"]):
                                st_id = "official_store_id" in rr["body"] and rr["body"]["official_store_id"]
                                ml_id = "id" in rr["body"] and rr["body"]["id"]
                                if (st_id and official_store_id and str(st_id)==str(official_store_id) ):
                                    rresults.append(ml_id)
                ids = ""
                n20 = 0
        #_logger.info("rresults:"+str(rresults))

        return rresults



    #Toma y lista los ids de las publicaciones del sitio de MercadoLibre, filtrados por official_store_id
    def fetch_list_meli_ids( self, params=None ):

        account = self

        if not params:
            params = {}

        company = account.company_id or self.env.user.company_id

        meli = self.env['meli.util'].get_new_instance( company, account )
        if meli.need_login():
            return meli.redirect_login()

        config = account.configuration
        official_store_id = config.mercadolibre_official_store_id or None

        response = meli.get("/users/"+str(account.seller_id)+"/items/search",
                            {'access_token':meli.access_token,
                            'search_type': 'scan',
                            'limit': 100, #max paging limit is always 100
                            **params })

        rjson = response.json()
        scroll_id = ""
        results = []
        ofresults = (rjson and "results" in rjson and rjson["results"]) or []
        filt_results = self.filter_meli_ids(  ofresults, store_id=official_store_id  )
        results+= filt_results or []
        condition_last_off = True
        total = (rjson and "paging" in rjson and "total" in rjson["paging"] and rjson["paging"]["total"]) or 0
        _logger.info("fetch_list_meli_ids: params:"+str(params)+" total:"+str(total))

        if (rjson and 'scroll_id' in rjson ):
            scroll_id = rjson['scroll_id']
            condition_last_off = False

        while (condition_last_off!=True):
            search_params = {
                'access_token': meli.access_token,
                'search_type': 'scan',
                'limit': 100,
                'scroll_id': scroll_id,
                **params
            }
            response = meli.get("/users/"+str(account.seller_id)+"/items/search", search_params )
            rjson2 = response.json()
            if (rjson2 and 'error' in rjson2):
                _logger.error(rjson2)
                if rjson2['message']=='invalid_token' or rjson2['message']=='expired_token':
                    ACCESS_TOKEN = ''
                    REFRESH_TOKEN = ''
                    account.write({'access_token': ACCESS_TOKEN, 'refresh_token': REFRESH_TOKEN, 'code': '' } )
                    condition = True
                    url_login_meli = meli.auth_url()
                    return {
                        "type": "ir.actions.act_url",
                        "url": url_login_meli,
                        "target": "new",}
                condition_last_off = True
            else:
                #results+= (rjson2 and "results" in rjson2 and rjson2["results"]) or []

                ofresults = (rjson2 and "results" in rjson2 and rjson2["results"]) or None
                filt_results = self.filter_meli_ids(  ofresults, store_id=official_store_id  )
                results+= filt_results or []
                condition_last_off = (total>0 and len(results)>=total)

        return results


    def fetch_list_meli_ids_maestro( self, params = None ):

        account = self
        maestros = self.env["mercadolibre.product.maestro"]
        meli_ids_maestros = []

        if not account:
            return []

        domain_account = [('connection_account','=',account.id)]
        domain_is_master = [('is_master','=',True)]
        domain_is_not_master = [('is_master','=',False)]
        domain_is_combo = [('is_combo','=',True)]
        domain_is_not_combo = [('is_combo','=',False)]

        domain_master_nocombos = domain_account + domain_is_master + domain_is_not_combo
        domain_master_combos = domain_account + domain_is_master + domain_is_combo
        domain_no_master_nocombos = domain_account + domain_is_not_master + domain_is_not_combo
        domain_no_master_combos = domain_account + domain_is_not_master + domain_is_combo

        melis_nocombos = maestros.search(domain_master_nocombos)
        melis_combos = maestros.search(domain_master_combos)
        melis_no_master_nocombos = maestros.search(domain_no_master_nocombos)
        melis_no_master_combos = maestros.search(domain_no_master_combos)

        if (melis_nocombos):
            meli_ids_maestros+= melis_nocombos.mapped('meli_id')

        if (melis_combos):
            meli_ids_maestros+= melis_combos.mapped('meli_id')

        if (melis_no_master_nocombos):
            meli_ids_maestros+= melis_no_master_nocombos.mapped('meli_id')

        if (melis_no_master_combos):
            meli_ids_maestros+= melis_no_master_combos.mapped('meli_id')

        _logger.info(" fetch_list_meli_ids_maestro > " + str(meli_ids_maestros))

        return meli_ids_maestros


    def record_maestro_review( self, meli_id, meli = None, rjson = None ):
        recorded = None
        maestros = self.env["mercadolibre.product.maestro"]
        domainaccount = [('connection_account','=',self.id)]

        _logger.info("record_maestro_review: "+str(meli_id))

        if (not rjson):
            _logger.error("Error rjson none")

        if (rjson):
            _logger.info("checking rjson! ")
            #recs = maestros.search([('meli_id','=',meli_id)])
            #if not recs:
            if ("variations" in rjson and rjson["variations"]):
                _logger.info("checking variations! "+str(rjson["variations"]))
                for var in rjson["variations"]:
                    if ( ("seller_sku" in var and var["seller_sku"]) or ("barcode" in var and var["barcode"]) ):
                        _logger.info("checking variations ! seller_sku: "+str(var))
                        ssku = ("seller_sku" in var and var["seller_sku"]) and (var["seller_sku"])
                        record = {
                            "connection_account": self.id,
                            "name":  rjson["title"]+str(" <C>"),
                            "meli_id": meli_id,
                            "meli_id_variation": var["id"],
                            "sku": ssku,
                            "barcode": ("barcode" in var and var["barcode"]) or None
                        }
                        rec = maestros.search( [('meli_id','=ilike',record["meli_id"]),('meli_id_variation','=ilike',record["meli_id_variation"])], limit=1)
                        if rec:
                            _logger.info("Founded! "+str(rec.connection_account))
                            record["name"] = rec.name
                            if (str(rec.sku)!=str(record["sku"]) or
                                str(rec.barcode)!=str(record["barcode"])):
                                _logger.info("Error no coinciden sku o barcode con la publicacion...")
                                _logger.info(record)
                            else:
                                record["sku"] = rec.sku
                                record["barcode"] = rec.barcode
                                rec.write(record)
                        else:
                            rec = maestros.search( [('meli_id','=ilike',record["meli_id"]),'|',('sku','=ilike',record["sku"]),('barcode','=ilike',record["barcode"])], limit=1)
                            if not rec:
                                _logger.info("Creating! ")
                                recorded = maestros.create( record )
                            else:
                                _logger.info("Founded! "+str(rec.connection_account))
                                record["name"] = rec.name
                                if (str(rec.sku)!=str(record["sku"]) or
                                    str(rec.barcode)!=str(record["barcode"])):
                                    _logger.info("Error no coinciden sku o barcode con la publicacion...")
                                    _logger.info(record)
                                else:
                                    record["sku"] = rec.sku
                                    record["barcode"] = rec.barcode
                                    rec.write(record)
                    else:
                        _logger.info("checking variations ! no seller_sku: "+str(var))
                        record = {
                            "connection_account": self.id,
                            "name":  rjson["title"]+str(" <C><I>"),
                            "meli_id": meli_id,
                            "meli_id_variation": var["id"],
                            "sku": "--SIN SKU--",
                            "barcode": "--SIN BARCODE--",
                            #"barcode": ("barcode" in var and var["barcode"]) or None
                        }
                        _logger.info("checking variations ! no seller_sku: "+str(rec))
                        rec = maestros.search( [('meli_id','=ilike',record["meli_id"]),('meli_id_variation','=ilike',record["meli_id_variation"])], limit=1)
                        if not rec:
                            _logger.info("Creating! ")
                            recorded = maestros.create( record )
                        else:
                            _logger.info("Founded! "+str(rec.connection_account))

                _logger.info("checking variations! ended")
            else:
                _logger.info("checking single variant! ")
                if ("seller_sku" in rjson and rjson["seller_sku"] or ("barcode" in rjson and rjson["barcode"]) ):
                    seller_sku = "seller_sku" in rjson and rjson["seller_sku"]
                    barcode =  ("barcode" in rjson and rjson["barcode"])
                    record = {
                        "connection_account": self.id,
                        "name":  rjson["title"]+str(" <C>"),
                        "meli_id": meli_id,
                        "meli_id_variation": None,
                        "sku": seller_sku,
                        "barcode": barcode
                    }
                    rec = maestros.search( [('meli_id','=ilike',record["meli_id"]),'|',('sku','=ilike',record["sku"]),('barcode','=ilike',record["barcode"])], limit=1)
                    if not rec:
                        _logger.info("Creating! ")
                        recorded = maestros.create( record )
                    else:
                        _logger.info("Founded! "+str(rec.connection_account))
                else:
                    record = {
                        "connection_account": self.id,
                        "name":  rjson["title"]+str(" <C><I>"),
                        "meli_id": meli_id,
                        "meli_id_variation": None,
                        "sku": "--SIN SKU--",
                        "barcode": "--SIN BARCODE--"
                    }
                    rec = maestros.search( [('meli_id','=ilike',record["meli_id"]),'|',('sku','=ilike',record["sku"]),('barcode','=ilike',record["barcode"])], limit=1)
                    if not rec:
                        _logger.info("Creating! ")
                        recorded = maestros.create( record )
                    else:
                        _logger.info("Founded! "+str(rec.connection_account))
        #self._cr.commit()

        return recorded

    def get_maestro( self, meli_id, meli = None, rjson = None  ):
        mas = None
        maestros = self.env["mercadolibre.product.maestro"]
        mas = maestros.search( [('meli_id','=',meli_id),('is_master','=',True)], limit=1 )
        return mas

    #list all meli ids in odoo from this account, that are not in parameter filter_ids...
    def list_meli_ids( self, filter_ids=None ):
        meli_ids = []
        account = self
        if not filter_ids:
            bindings = self.env['mercadolibre.product_template'].search([ ('connection_account','=',account.id),
                                                                        ('product_tmpl_id','!=', False),
                                                                        ('conn_id','!=',False)
                                                                        ])
        else:
            bindings = self.env['mercadolibre.product_template'].search([ ('connection_account','=',account.id),
                                                                        ('product_tmpl_id','!=', False),
                                                                        ('conn_id','not in',filter_ids),
                                                                        ('conn_id','!=',False)
                                                                        ])
        if bindings:
            meli_ids = bindings.mapped('conn_id')

        return meli_ids

    def product_meli_get_products(self, context=None, limit=50):
        #
        account = self
        context = context or self.env.context
        _logger.info('account.product_meli_get_products() '+str(account.name)+" context:"+str(context))
        company = account.company_id or self.env.user.company_id
        product_obj = self.pool.get('product.product')
        warningobj = self.env['meli.warning']

        post_state = context and context.get("post_state")
        meli_id = context and context.get("meli_id")
        force_create_variants = context and context.get("force_create_variants")
        force_dont_create = context and context.get("force_dont_create")
        force_meli_pub =  context and context.get("force_meli_pub")
        force_meli_website_published = context and context.get("force_meli_website_published")
        force_meli_website_category_create_and_assign = context and context.get("force_meli_website_category_create_and_assign")
        batch_processing_unit = context and context.get("batch_processing_unit")
        batch_processing_unit_offset = context and context.get("batch_processing_unit_offset")
        batch_actives_to_sync = context and context.get("batch_actives_to_sync")
        batch_paused_to_sync = context and context.get("batch_paused_to_sync")
        batch_left_to_sync = context and context.get("batch_left_to_sync")
        search_limit = batch_processing_unit or 100
        search_offset = batch_processing_unit_offset or 0

        actives_to_sync = []
        odoo_meli_ids = []

        #Lets list all the already imported meli publications
        if (batch_actives_to_sync or batch_paused_to_sync or batch_left_to_sync):
            odoo_meli_ids = odoo_meli_ids or account.list_meli_ids()

        _logger.info("batch_processing_unit:"+str(batch_processing_unit)+" search_offset:"+str(search_offset)+" search_limit:"+str(search_limit))

        meli = self.env['meli.util'].get_new_instance( company, account )
        if meli.need_login():
            return meli.redirect_login()

        results = []

        post_state_filter = {}
        if post_state:
            if post_state=='active' or batch_actives_to_sync:
                post_state_filter = { 'status': 'active' }
            elif post_state=='paused' or batch_paused_to_sync:
                post_state_filter = { 'status': 'paused' }
            elif post_state=='closed':
                post_state_filter = { 'status': 'closed' }
        if meli_id:
            post_state_filter.update( { 'meli_id': meli_id } )

        official_store_id = (account.official_store_id) or None

        url_get = "/users/"+str(account.seller_id)+"/items/search"

        #_logger.info(meli.access_token)
        meli_ids = self.fetch_list_meli_ids( params=post_state_filter )
        _logger.info("meli_ids "+str(meli_ids and len(meli_ids) or 0)+" > "+str(meli_ids))
        meli_ids_maestros = self.fetch_list_meli_ids_maestro( params=post_state_filter )
        _logger.info("meli_ids_maestros "+str(meli_ids_maestros and len(meli_ids_maestros) or 0)+" > "+str(meli_ids_maestros))

        #check
        meli_ids_maestros_checked = []
        meli_ids_maestros_active = meli_ids_maestros and len(meli_ids_maestros)
        if (meli_ids_maestros_active):
            #nos aseguramos procesar en orden las publicaciones de los maestros:
            for mid in meli_ids_maestros:
                if mid in meli_ids:
                    if mid not in meli_ids_maestros_checked:
                        meli_ids_maestros_checked.append(mid)
            #agregamos los rezagados
            for mid in meli_ids:
                if mid not in meli_ids_maestros_checked:
                    meli_ids_maestros_checked.append(mid)

            meli_ids = meli_ids_maestros_checked
        _logger.info("meli_ids_maestros_checked "+str(meli_ids_maestros_checked and len(meli_ids_maestros_checked) or 0)+" > "+str(meli_ids_maestros_checked))
        _logger.info("meli_ids_maestros_active "+str(meli_ids_maestros_active))

        #download?
        totalmax = len(meli_ids)
        offset = search_offset

        _logger.info( "totalmax: "+str(totalmax)+" offset:"+str(offset) )

        if (totalmax>1):
            #USE SCAN METHOD.... ALWAYS
            condition_last_off = True
            ioff = 0
            cof = 0
            results = []

            for meli_id in meli_ids:
                ioff = cof
                if meli_id:
                    if ( cof>=offset and meli_id not in odoo_meli_ids ):
                        results.append( meli_id )
                    cof+= 1

                if (batch_processing_unit and batch_processing_unit>0 and results and len(results)>=batch_processing_unit):
                    break;


        #search for meli_ids not imported yet
        binding_meli_ids  = account.list_meli_ids(filter_ids=results)

        _logger.info( results )
        _logger.info( "FULL RESULTS: " + str(len(results)) + " News: " + str(len(binding_meli_ids)) )
        #_logger.info( binding_meli_ids )
        _logger.info( "("+str(totalmax)+") products to check...")


        if binding_meli_ids and (not batch_processing_unit or batch_processing_unit==0):
            #assigning missing meli ids, shapes, and colors
            _logger.info( "results, not batch_processing_unit, assigning binding_meli_ids: "+str(binding_meli_ids))
            results = binding_meli_ids

        totalmax = len(results)
        iitem = 0
        icommit = 0
        micom = 5

        duplicates = []
        missing = []
        synced = []
        res = {}
        if (results):
            Autocommit( self )
            try:
                _logger.info("results: "+str(results))
                for item_id in results:
                    #_logger.info("item_id: "+str(item_id))
                    iitem+= 1
                    icommit+= 1
                    if (icommit>=micom):
                        self._cr.commit()
                        icommit = 0
                    _logger.info( item_id + " >>>> ("+str(iitem)+"/"+str(totalmax)+")" )

                    #check first if we have variations...
                    #we have a meli_id > an item w/wout variations >
                    rjson = account.fetch_meli_product( meli_id = item_id, meli=meli )
                    rjson_has_variations = rjson and "variations" in rjson and len(rjson["variations"])

                    seller_sku = None

                    if not seller_sku and "attributes" in rjson:
                        for att in rjson['attributes']:
                            if att["id"] == "SELLER_SKU":
                                seller_sku = att["values"][0]["name"]
                                break;

                    if (not seller_sku and 'seller_custom_field' in rjson and rjson['seller_custom_field'] and len(rjson['seller_custom_field'])):
                        seller_sku = rjson['seller_custom_field']

                    seller_sku = account.fetch_meli_sku(meli_id=item_id, meli_id_variation = None, meli=meli, rjson=rjson)

                    product_id, binding_id  = account.search_meli_product( meli_id = item_id, meli=meli, rjson=rjson )
                    #posting_id = self.env['product.product'].search([('meli_id','=',item_id)])

                    if product_id:
                        UpdateProductType( product_id )

                    if (product_id or force_dont_create):

                        if (product_id and len(product_id)>1):
                            duplicates.append({
                                            'name': str(product_id[0].name),
                                            'default_code': str(product_id[0].default_code),
                                            'meli_sku': str(seller_sku or ''),
                                            'meli_id': item_id,
                                            'meli_id_variation': product_id[0].meli_id_variation,
                                            'meli_status': rjson['status'],
                                            'status': 'duplicate',
                                            })
                            _logger.error( "Item already in database but duplicated: " + str(product_id.mapped('name')) + " skus:" + str(product_id.mapped('default_code')) )

                        if product_id and len(product_id)==1:

                            UpdateProductType( product_id )

                            _logger.info( "Item(s) already in database: " + str(product_id.mapped('display_name')) + str(" #")+str(len(product_id)) )

                            if force_meli_pub:
                                _logger.info( "Item meli_pub set" )
                                product_id.meli_pub = True
                                product_id.product_tmpl_id.meli_pub = True

                            synced.append( {
                                            'name': str(product_id.name),
                                            'default_code': str(product_id.default_code),
                                            'meli_sku': str(seller_sku or ''),
                                            'meli_id': item_id,
                                            'meli_id_variation': product_id.meli_id_variation,
                                            'meli_status': rjson['status'] ,
                                            'status': 'synced'
                                            })

                            #3 casos: el producto en ML tiene variantes,

                            #TODO: here set skus...

                            #TODO: fix bindings
                            #if not binding_id:
                                #auto bind
                            bind_only = False
                            if rjson_has_variations:
                                _logger.info( "Binding variations: oldies: " + str(binding_id and binding_id.mapped('name')) + str(" binding_id:")+str(binding_id) )
                                if binding_id:
                                    _logger.info( "Item(s) already binded: " + str(binding_id.mapped('name')) + str(" #")+str(len(binding_id)) )
                                    bind_only = True
                                for product in product_id:
                                    pvbind = product.mercadolibre_bind_to( account=account, meli_id = item_id, meli=meli, rjson=rjson, bind_only=bind_only )
                            else:
                                pvbind = product_id[0].mercadolibre_bind_to( account=account, meli_id = item_id, meli=meli, rjson=rjson, bind_only=bind_only)

                        else:
                            missing.append({
                                            'name': rjson['title'],
                                            'default_code': '',
                                            'meli_sku': str(seller_sku or ''),
                                            'meli_id': item_id,
                                            'meli_id_variation': '',
                                            'meli_status': rjson['status'] ,
                                            'status': 'missing'
                                            })
                            _logger.info( "Item not in database, no sync founded for meli_id: "+str(item_id) + " seller_sku: " +str(seller_sku) )
                        #rewrite, maybe update data from rjson... not in template but in bindings...
                        #if binding_id:
                        #    product_id[0].mercadolibre_bind_to( account=account, meli_id = item_id)
                    #elif (not company.mercadolibre_import_search_sku):

                        _logger.info("Product "+str(product_id))
                        _logger.info("Binding "+str(binding_id))

                        if (meli_ids_maestros_active):
                            if (item_id in meli_ids_maestros):
                                _logger.info("Product is in maestro already as a publication but checking if its complete: "+str(item_id) )
                                account.record_maestro_review( meli_id = item_id, meli=meli, rjson=rjson )
                            else:
                                _logger.info("Product is NOT in maestro already, register it: "+str(item_id) )
                                #product_id, binding_id
                                account.record_maestro_review( meli_id = item_id, meli=meli, rjson=rjson )

                    else:
                        if (official_store_id and "official_store_id" in rjson and str(official_store_id)!=str(rjson["official_store_id"])):
                            continue;
                        #idcreated = self.pool.get('product.product').create(cr,uid,{ 'name': rjson3['title'], 'meli_id': rjson3['id'] })
                        try:
                            #solo crear productos si esta en el maestro
                            if (meli_ids_maestros_active):
                                if (item_id in meli_ids_maestros):
                                    #busca el que es is_master true
                                    el_maestro = account.get_maestro(item_id)
                                    _logger.info("el_maestro: "+str(el_maestro))
                                    _logger.info("el_maestro meli_id: "+str(item_id))
                                    _logger.info("el_maestro.is_master: "+str(el_maestro.is_master))
                                    _logger.info("el_maestro.is_valid: "+str(el_maestro.is_valid))

                                    if (el_maestro and el_maestro.is_master and el_maestro.is_valid):
                                        _logger.info("creando: "+str(el_maestro))
                                        account.create_meli_product( meli_id = item_id, meli=meli, rjson=rjson )
                                    else:
                                        _logger.info("no se pudo crear")
                                        #porque?


                                else:
                                    _logger.info("Meli Id not in maestro, record it: "+str(item_id))
                                    account.record_maestro_review( meli_id = item_id, meli=meli, rjson=rjson )
                            else:
                                _logger.info("Creating meli product (no maestros yet)")
                                account.create_meli_product( meli_id = item_id, meli=meli, rjson=rjson )
                        except Exception as e:
                            _logger.error("product_meli_get_products create_meli_product Exception!")
                            _logger.error(e, exc_info=True)
                            #self._cr.rollback()
                    _logger.info("##########")

                _logger.info("Synced: "+str(synced))
                _logger.info("Duplicates: "+str(duplicates))
                _logger.info("Missing: "+str(missing))
            except Exception as e:
                _logger.error("product_meli_get_products Exception!")
                _logger.error(e, exc_info=True)
                _logger.info("Synced: "+str(synced))
                _logger.info("Duplicates: "+str(duplicates))
                _logger.info("Missing: "+str(missing))
                self._cr.rollback()

            html_report = "<h2>Reporte Importación</h2>"

            html_report+= "<h4>Syncronizados</h4>"
            for pub in synced:
                #
                html_report+= "<br/> meli_id: "+pub['meli_id']+" name:"+pub['name']+ " meli_sku:"+pub["meli_sku"]

            html_report+= "<h4>Duplicados</h4>"
            for pub in duplicates:
                #
                html_report+= "<br/> meli_id: "+pub['meli_id']+" name:"+pub['name']+ " meli_sku:"+pub["meli_sku"]

            html_report+= "<h4>Faltantes</h4>"
            for pub in missing:
                #
                html_report+= "<br/> meli_id: "+pub['meli_id']+" name:"+pub['name']+ " meli_sku:"+pub["meli_sku"]


            res = warningobj.info( title='MELI INFO IMPORT',
                                          message="Reporte de Importación",
                                          message_html=""+html_report )
            if batch_processing_unit and batch_processing_unit>0:
                res = {
                #    "type": "set_scrollTop",
                }
            res.update( {
                'html_report': html_report,
                'paging': {
                    'offset': search_offset,
                    'next_offset': search_offset+search_limit,
                    'limit': search_limit
                },
                'json_report': {
                    'synced': synced,
                    'duplicates': duplicates,
                    'missing': missing
                    }
                })
            _logger.info(res)
        return res

    def meli_update_remote_products( self, post_new=False ):
        #
        _logger.info("meli_update_remote_products")

    def meli_update_remote_stock(self, meli=False):
        account = self
        _logger.info('account.meli_update_remote_stock() STARTED '+str(account.name) + " " +str( datetime.now() ))
        company = account.company_id or self.env.user.company_id
        config = account.configuration or company
        notilog = True
        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            #if meli.need_login():
            #    return meli.redirect_login()

        if (config.mercadolibre_cron_post_update_stock):
            auto_commit = not getattr(threading.currentThread(), 'testing', False)
            topcommits = 40

            product_bind_ids_status_to_update_ids = []
            if (1==2):
                product_bind_ids_status_to_update = self.env['mercadolibre.product'].search([
                    ('meli_id','!=',False),
                    ('meli_id','!=',''),
                    ('connection_account', '=', account.id ),
                    ('meli_stock_status','=','update')
                    ], order='stock_update asc',limit=topcommits)

                product_bind_ids_status_to_update_ids = product_bind_ids_status_to_update.mapped("id")

            #query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update, pp.active  FROM   mercadolibre_product as melip, product_product as pp WHERE melip.product_id=pp.id AND pp.active IS TRUE AND melip.connection_account=%i AND melip.meli_id!='' AND NOT melip.meli_id IS NULL AND melip.stock_update IS NULL""" % (account.id)
            query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update, pp.active
            FROM   mercadolibre_product as melip, product_product as pp
            WHERE
            melip.product_id=pp.id
            AND pp.active IS TRUE
            AND melip.connection_account=%i
            AND melip.meli_id!=''
            AND NOT melip.meli_id IS NULL
            AND melip.meli_stock_status = 'update'""" % (account.id)
            cr = self._cr
            respquery = cr.execute(query)
            results = cr.fetchall()
            product_bind_ids_null = results

            _logger.info("query: "+str(query)+" results update null:"+str(results))

            #query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update, pp.active  FROM   mercadolibre_product as melip, product_product as pp WHERE melip.product_id=pp.id AND pp.active IS TRUE AND melip.connection_account=%i AND melip.meli_id!='' AND NOT melip.meli_id IS NULL AND melip.stock_update IS NOT NULL""" % (account.id)
            query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update, pp.active
            FROM   mercadolibre_product as melip, product_product as pp
            WHERE
            melip.product_id=pp.id
            AND pp.active IS TRUE
            AND melip.connection_account=%i
            AND melip.meli_id!=''
            AND NOT melip.meli_id IS NULL
            AND melip.meli_stock_status != 'update'
            AND melip.meli_stock_status != 'updated'
            AND melip.meli_stock_status != 'revision_fullfilment'
            AND melip.meli_stock_status != 'revision_error'
            AND melip.meli_stock_status != 'revision_unmoved'""" % (account.id)
            #query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update, pp.active  FROM   mercadolibre_product as melip, product_product as pp WHERE melip.product_id=pp.id AND pp.active IS TRUE AND melip.connection_account=%i AND melip.meli_id!='' AND NOT melip.meli_id IS NULL AND melip.meli_stock_status != 'update' AND melip.meli_stock_status != 'updated'""" % (account.id)
            cr = self._cr
            respquery = cr.execute(query)
            results = cr.fetchall()
            product_bind_ids_not_null = results

            _logger.info("query: "+str(query)+" results update not null:"+str(results))

            query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update, pp.active
            FROM   mercadolibre_product as melip, product_product as pp
            WHERE
            melip.product_id=pp.id
            AND pp.active IS TRUE
            AND melip.connection_account=%i
            AND melip.meli_id!=''
            AND NOT melip.meli_id IS NULL
            AND melip.meli_stock_status IS NULL""" % (account.id)
            #query = """SELECT melip.id, melip.connection_account, melip.meli_id, melip.stock_update, pp.active  FROM   mercadolibre_product as melip, product_product as pp WHERE melip.product_id=pp.id AND pp.active IS TRUE AND melip.connection_account=%i AND melip.meli_id!='' AND NOT melip.meli_id IS NULL AND melip.meli_stock_status != 'update' AND melip.meli_stock_status != 'updated'""" % (account.id)
            cr = self._cr
            respquery = cr.execute(query)
            results = cr.fetchall()
            product_bind_ids_not_null+= results
            _logger.info("query: "+str(query)+" results null:"+str(results))

            #return {}
            """
            product_bind_ids_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                ('meli_id','!=',False),
                ('meli_id','!=',''),
                ('connection_account', '=', account.id ),
                ('stock_update','=',False),
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='id asc',limit=topcommits)
            """
            """
            product_bind_ids_not_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                ('meli_id','!=',False),
                ('meli_id','!=',''),
                ('connection_account', '=', account.id ),
                ('stock_update','!=',False)
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='stock_update asc',limit=topcommits)
            """
            product_bind_ids = product_bind_ids_null + product_bind_ids_not_null

            _logger.info("product_bind_ids stock to update:" + str(product_bind_ids))
            _logger.info("account updating stock #" + str(len(product_bind_ids)) + " on " + str(account.name))
            icommit = 0
            icount = 0
            maxcommits = len(product_bind_ids)
            internals = {
                "application_id": account.client_id,
                "user_id": account.seller_id,
                "topic": "internal",
                "resource": "meli_update_remote_stock #"+str(maxcommits),
                "state": "PROCESSING"
            }
            noti = False
            if (notilog):
                noti = self.env["mercadolibre.notification"].start_internal_notification( internals=internals, account=account )
            logs = ""
            errors = ""

            try:
                if auto_commit:
                    self.env.cr.commit()
                for bindx in product_bind_ids:
                    bind = self.env['mercadolibre.product'].browse(bindx[0])
                    obj = bind #.product_id
                    #_logger.info( "Product check if active: " + str(obj.id)+ ' meli_id:'+str(obj.meli_id)  )
                    if (obj and obj.meli_id and icount<=topcommits):
                        icommit+= 1
                        icount+= 1
                        try:
                            _logger.info( "Update Stock: #" + str(icount) +'/'+str(maxcommits)+ ' meli_id:'+str(obj.meli_id)  )
                            resjson = obj.product_post_stock(meli=meli)
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+"\n"
                            if resjson and "error" in resjson:
                                errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(resjson)+"\n"
                            #obj.stock_update = ml_datetime( str( datetime.now() ) )

                            if ((icommit==10 or (icount==maxcommits) or (icount==topcommits)) and 1==1):
                                noti.processing_errors = errors
                                noti.processing_logs = logs
                                noti.resource = "meli_update_remote_stock #"+str(icount) +'/'+str(maxcommits)
                                _logger.info("meli_update_remote_stock commiting")
                                icommit=0
                                if auto_commit:
                                    self.env.cr.commit()

                        except Exception as e:
                            _logger.info("meli_update_remote_stock > Exception founded!")
                            _logger.info(e, exc_info=True)
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+", "
                            #errors+= str(obj.default_code)+" "+str(obj.meli_id)+" >> "+str(e.args[0])+str(", ")
                            errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(e)+"\n"
                            if auto_commit:
                                self.env.cr.rollback()

                if (notilog):
                    noti.resource = "meli_update_remote_stock #"+str(icount) +'/'+str(maxcommits)
                    noti.stop_internal_notification(errors=errors,logs=logs)

            except Exception as e:
                _logger.info("meli_update_remote_stock > Exception founded!")
                _logger.info(e, exc_info=True)
                if auto_commit:
                    self.env.cr.rollback()
                if (notilog):
                    noti.stop_internal_notification( errors=errors , logs=logs )
                if auto_commit:
                    self.env.cr.commit()

        _logger.info('account.meli_update_remote_stock() ENDED '+str(account.name) + " " +str( datetime.now() ))
        return {}

    def meli_update_remote_stock_injobs(self, meli=False, notification=None):
        account = self
        _logger.info('account.meli_update_remote_stock_injobs() '+str(account.name))
        company = account.company_id or self.env.user.company_id
        config = account.configuration or company

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            #if meli.need_login():
            #    return meli.redirect_login()

        noti_ids = (notification and [('id','=',notification.id)] ) or []
        _logger.info('account.meli_update_remote_stock_injobs() mercadolibre_cron_post_update_stock: '+str(config.mercadolibre_cron_post_update_stock)+" noti_ids: "+str(noti_ids))
        if (config.mercadolibre_cron_post_update_stock):
            auto_commit = not getattr(threading.currentThread(), 'testing', False)

            icommit = 0
            icount = 0
            notifs = self.env["mercadolibre.notification"].search( noti_ids + [('topic','=','internal_job'),
                                                                ('resource','like','meli_update_remote_stock%'),
                                                                ('state','!=','SUCCESS'),
                                                                ('state','!=','FAILED'),
                                                                ('connection_account','=',account.id) ],
                                                                limit=40)

            _logger.info("meli_update_remote_stock_injobs > internal_job meli_update_remote_stock: "+str(notifs)+" state:"+str(notifs.mapped('state')) )

            if not notifs:
                _logger.info("meli_update_remote_stock_injobs > internal_job meli_update_remote_stock: NO stock internal_job.")
                return {}

            max_ustocks = 100
            actual_ustock = 0
            full_pids = []
            for noti in notifs:

                product_ids = (noti.model_ids and json.loads(noti.model_ids)) or []
                product_ids_processed = (noti.model_ids_processed and json.loads(noti.model_ids_processed)) or []
                notpids = (product_ids_processed and [('product_ids','not in', product_ids_processed)]) or []

                #filtering processed
                pids = []
                for p in product_ids:
                    if p not in product_ids_processed and p not in pids and p not in full_pids:
                        pids.append(p)
                        full_pids.append(p)

                product_ids = pids

                _logger.info("Processing model_ids (product.product) : "+str(product_ids))
                product_bind_ids = self.env['mercadolibre.product'].search([
                    ##('connection_account', '=', account.id )
                    ##'|',('company_id','=',False),('company_id','=',company.id)
                    ('product_id', 'in', product_ids )],
                    order='stock_update asc, product_id asc')
                _logger.info("product_bind_ids stock to update:" + str(product_bind_ids))
                _logger.info("account updating stock #" + str(len(product_bind_ids)) + " on " + str(account.name))
                _logger.info("product_ids: "+str(product_ids))
                _logger.info("product_ids_processed: "+str(product_ids_processed))
                _logger.info("notpids: "+str(notpids))
                _logger.info("product_bind_ids: "+str(product_bind_ids))
                maxcommits = len(product_bind_ids)
                logs = noti.processing_logs or ""
                errors = noti.processing_errors or ""

                try:
                    if auto_commit:
                        self.env.cr.commit()
                    pid = None
                    for bind in product_bind_ids:
                        obj = bind #.product_id
                        #_logger.info( "Product check if active: " + str(obj.id)+ ' meli_id:'+str(obj.meli_id)  )
                        if (obj and obj.meli_id):
                            icommit+= 1
                            icount+= 1
                            actual_ustock+= 1
                            try:
                                _logger.info( "Update Stock: #" + str(icount) +'/'+str(maxcommits)+ ' meli_id:'+str(obj.meli_id)  )
                                resjson = obj.product_post_stock(meli=meli)
                                logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+"\n"
                                if resjson and "error" in resjson:
                                    errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(resjson)+"\n"
                                #obj.stock_update = ml_datetime( str( datetime.now() ) )

                                #record product processed by bindings
                                if (pid==None):
                                    pid = obj.product_id.id
                                if (pid!=obj.product_id.id or icount==maxcommits) and obj.product_id.id not in product_ids_processed:
                                    product_ids_processed.append(obj.product_id.id)
                                    _logger.info("product_ids_processed: #"+str(len(product_ids_processed)))
                                pid = obj.product_id.id

                                if ( (actual_ustock>=max_ustocks) or (icommit==40 or (icount==maxcommits) or (icount==noti.model_ids_step))  and 1==1):
                                    noti.processing_errors = errors
                                    noti.processing_logs = logs
                                    noti.model_ids_processed = str(product_ids_processed)
                                    noti.model_ids_count_processed = len(product_ids_processed)
                                    noti.resource = "meli_update_remote_stock #"+str(icount) +'/'+str(maxcommits)
                                    _logger.info("meli_update_remote_stock_injobs commiting")
                                    icommit=0
                                    if auto_commit:
                                        self.env.cr.commit()
                                    #max steps by iteration reached
                                    if (icount>=noti.model_ids_step and icount<maxcommits):
                                        return {}
                                    #max updates on cron iteration reached:
                                    if (actual_ustock>=max_ustocks):
                                        _logger.info("meli_update_remote_stock_injobs max_ustocks reached:"+str(max_ustocks))
                                        return {}


                            except Exception as e:
                                _logger.info("meli_update_remote_stock > Exception founded!")
                                _logger.info(e, exc_info=True)
                                logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_available_quantity)+", "
                                #errors+= str(obj.default_code)+" "+str(obj.meli_id)+" >> "+str(e.args[0])+str(", ")
                                errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(e)+"\n"
                                if auto_commit:
                                    self.env.cr.rollback()

                    noti.resource = "meli_update_remote_stock_injobs #"+str(icount) +'/'+str(maxcommits)
                    noti.stop_internal_notification(errors=errors,logs=logs)

                except Exception as e:
                    _logger.info("meli_update_remote_stock_injobs > Exception founded!")
                    _logger.info(e, exc_info=True)
                    if auto_commit:
                        self.env.cr.rollback()
                    noti.stop_internal_notification( errors=errors , logs=logs )
                    if auto_commit:
                        self.env.cr.commit()

        return {}

    def meli_update_remote_price(self, meli=None):

        account = self
        _logger.info('account.meli_update_remote_price() STARTED '+str(account.name))
        company = account.company_id or self.env.user.company_id
        config = account.configuration or company

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )
            #if meli.need_login():
            #    return meli.redirect_login()

        if (config.mercadolibre_cron_post_update_price):
            auto_commit = not getattr(threading.currentThread(), 'testing', False)
            topcommits = 80
            product_bind_ids_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                #('meli_id','!=',False),
                ('connection_account', '=', account.id ),
                ('price_update','=',False),
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='price_update asc', limit=topcommits)
            product_bind_ids_not_null = self.env['mercadolibre.product'].search([
                #('meli_pub','=',True),
                #('meli_id','!=',False),
                ('connection_account', '=', account.id ),
                ('price_update','!=',False)
                #'|',('company_id','=',False),('company_id','=',company.id)
                ], order='price_update asc', limit=topcommits)
            product_bind_ids = product_bind_ids_null + product_bind_ids_not_null
            _logger.info("product_bind_ids price to update:" + str(product_bind_ids))
            _logger.info("account updating price #" + str(len(product_bind_ids)) + " on " + str(account.name))
            icommit = 0
            icount = 0
            maxcommits = len(product_bind_ids)
            internals = {
                "application_id": account.client_id,
                "user_id": account.seller_id,
                "topic": "internal",
                "resource": "meli_update_remote_price #"+str(maxcommits),
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals=internals, account=account )
            logs = ""
            errors = ""

            try:
                if auto_commit:
                    self.env.cr.commit()
                for bind in product_bind_ids:
                    #obj = product_bind_ids.product_id
                    obj = bind
                    #_logger.info( "Product check if active: " + str(obj.id)+ ' meli_id:'+str(obj.meli_id)  )
                    if (obj and obj.meli_id and icount<=topcommits):
                        icommit+= 1
                        icount+= 1
                        try:
                            _logger.info( "Update Price: #" + str(icount) +'/'+str(maxcommits)+ ' meli_id:'+str(obj.meli_id)  )
                            resjson = obj.product_post_price(meli=meli)
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_price)+"\n"
                            if not resjson or (resjson and "error" in resjson):
                                errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(resjson)+"\n"
                            else:
                                obj.price_update = ml_datetime( str( datetime.now() ) )

                            if ((icommit==40 or (icount==maxcommits) or (icount==topcommits)) and 1==1):
                                noti.processing_errors = errors
                                noti.processing_logs = logs
                                noti.resource = "meli_update_remote_price #"+str(icount) +'/'+str(maxcommits)
                                _logger.info("meli_update_remote_price commiting")
                                icommit=0
                                if auto_commit:
                                    self.env.cr.commit()

                        except Exception as e:
                            _logger.info("meli_update_remote_price > Exception founded!")
                            _logger.info(e, exc_info=True)
                            logs+= str(obj.sku)+" "+str(obj.meli_id)+": "+str(obj.meli_price)+", "
                            #errors+= str(obj.default_code)+" "+str(obj.meli_id)+" >> "+str(e.args[0])+str(", ")
                            errors+= str(obj.sku)+" "+str(obj.meli_id)+" >> "+str(e)+"\n"
                            if auto_commit:
                                self.env.cr.rollback()

                noti.resource = "meli_update_remote_price #"+str(icount) +'/'+str(maxcommits)
                noti.stop_internal_notification(errors=errors,logs=logs)

            except Exception as e:
                _logger.info("meli_update_remote_price > Exception founded!")
                _logger.info(e, exc_info=True)
                if auto_commit:
                    self.env.cr.rollback()
                noti.stop_internal_notification( errors=errors , logs=logs )
                if auto_commit:
                    self.env.cr.commit()

        return {}



#STANDARD




    def list_catalog( self, **post ):

        result = []

        _logger.info("list_catalog mercadolibre")
        #_logger.info(result)

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_catalog",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_catalog error creating notification: "+str(e))
            pass;

        for binding in bindings:

            product = binding.product_tmpl_id

            tpl = {
                "name": product.name or "",
                "code": product.default_code or "",
                "barcode": product.barcode or "",
                "brand": "Oneill",
                "variations": [],
                "category": product.categ_id.name or "",
                "notes": product.description_sale or "",
                "prices": [],
                "dimensions": {
                    "weight": 1,
                    "width": 1,
                    "length": 1,
                    "height": 1,
                    "pieces": 1
                },
                "attributes": []
            }

            prices = []
            #self.with_context(pricelist=pricelist.id).price
            #for plitem in product.item_ids:
            for pl in account.configuration.publish_price_lists:
                plprice = product.with_context(pricelist=pl.id).price
                price = {
                    "priceListId": pl.id,
                    "priceList": pl.name,
                    "amount": plprice,
                    "currency": pl.currency_id.name
                }
                prices.append(price)

            attributes = []
            attvariants = []
            for attline in product.attribute_line_ids:
                if len(attline.value_ids)>1:
                    attvariants.append(attline.attribute_id.id)
                else:
                    for val in attline.value_ids:
                        att = {
                            "key": attline.attribute_id.name,
                            "value": val.name
                        }
                        attributes.append(att)

            #tpl["variations"]
            for variant in product.product_variant_ids:

                var = {
                    "sku": variant.default_code or "",
                    #"color": "" or "",
                    #"size": "" or "",
                    "barcode": variant.barcode or "",
                    "code": variant.default_code or "",
                }

                for val in variant.attribute_value_ids:
                    if val.attribute_id.id in attvariants:
                        var[val.attribute_id.name] = val.name

                stocks = []
                #ss = variant._product_available()
                _logger.info("account.configuration.publish_stock_locations")
                _logger.info(account.configuration.publish_stock_locations.mapped("id"))
                sq = self.env["stock.quant"].search([('product_id','=',variant.id)])
                if (sq):
                    _logger.info( sq )
                    #_logger.info( sq.name )
                    for s in sq:
                        #TODO: filtrar por configuration.locations
                        #TODO: merge de stocks
                        #TODO: solo publicar available
                        if ( s.location_id.usage == "internal" and s.location_id.id in account.configuration.publish_stock_locations.mapped("id")):
                            _logger.info( s )
                            sjson = {
                                "warehouseId": s.location_id.id,
                                "warehouse": s.location_id.display_name,
                                "quantity": s.quantity,
                                "reserved": s.reserved_quantity,
                                "available": s.quantity - s.reserved_quantity
                            }
                            stocks.append(sjson)

                #{
                #    "warehouseId": 61879,
                #    "warehouse": "Estoque Principal - Ecommerce",
                #    "quantity": 0,
                #    "reserved": 0,
                #    "available": 0
                #}

                pictures = []
                if "product_image_ids" in variant._fields:
                    if variant.image:
                        img = {
                            "url": variant.mercadolibre_image_url_principal(),
                            "id": variant.mercadolibre_image_id_principal()
                        }
                        pictures.append(img)
                    for image in variant.product_image_ids:
                        img = {
                            "url": variant.mercadolibre_image_url(image),
                            "id": variant.mercadolibre_image_id(image)
                        }
                        pictures.append(img)

                var["pictures"] = pictures
                var["stocks"] = stocks

                tpl["variations"].append(var)

            tpl["prices"] = prices
            tpl["attributes"] = attributes

            result.append(tpl)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def list_pricestock( self, **post ):
        _logger.info("list_pricestock")
        result = []

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_pricestock",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_pricestock error creating notification: "+str(e))
            pass;

        for binding in bindings:

            variant = binding.product_id

            var = {
                "sku": variant.default_code or "",
                "barcode": variant.barcode or "",
            }

            stocks = []
            #ss = variant._product_available()
            sq = self.env["stock.quant"].search([('product_id','=',variant.id)])
            if (sq):
                _logger.info( sq )
                #_logger.info( sq.name )
                for s in sq:
                    if ( s.location_id.usage == "internal" and s.location_id.id in account.configuration.publish_stock_locations.mapped("id")):
                        _logger.info( s )
                        sjson = {
                            "warehouseId": s.location_id.id,
                            "warehouse": s.location_id.display_name,
                            "quantity": s.quantity,
                            "reserved": s.reserved_quantity,
                            "available": s.quantity - s.reserved_quantity
                        }
                        stocks.append(sjson)

            var["stocks"] = stocks

            prices = []
            for pl in account.configuration.publish_price_lists:
                plprice = variant.with_context(pricelist=pl.id).price
                price = {
                    "priceListId": pl.id,
                    "priceList": pl.name,
                    "amount": plprice,
                    "currency": pl.currency_id.name
                }
                prices.append(price)
            var["prices"] = prices

            result.append(var)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def list_pricelist( self, **post ):
        _logger.info("list_pricelist")
        result = []

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_pricelist",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_pricelist error creating notification: "+str(e))
            pass;

        for binding in bindings:

            variant = binding.product_id

            var = {
                "sku": variant.default_code or "",
                "barcode": variant.barcode or "",
            }

            prices = []
            for pl in account.configuration.publish_price_lists:
                plprice = product.with_context(pricelist=pl.id).price
                price = {
                    "priceListId": pl.id,
                    "priceList": pl.name,
                    "amount": plprice,
                    "currency": pl.currency_id.name
                }
                prices.append(price)
            var["prices"] = prices

            result.append(var)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def list_stock( self, **post ):
        _logger.info("list_stock")
        result = []

        account = self
        company = account.company_id or self.env.user.company_id
        bindings = self.env["mercadolibre.product"].search([("connection_account","=",account.id)])

        #start notification
        noti = None
        logs = ""
        errors = ""
        try:
            internals = {
                "connection_account": account,
                "application_id": account.client_id or '',
                "user_id": account.seller_id or '',
                "topic": "catalog",
                "resource": "list_stock",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("list_stock error creating notification: "+str(e))
            pass;

        for binding in bindings:

            variant = binding.product_id

            var = {
                "sku": variant.default_code or "",
                "barcode": variant.barcode or "",
            }


            stocks = []
            #ss = variant._product_available()
            sq = self.env["stock.quant"].search([('product_id','=',variant.id)])
            if (sq):
                _logger.info( sq )
                #_logger.info( sq.name )
                for s in sq:
                    if ( s.location_id.usage == "internal" and s.location_id.id in account.configuration.publish_stock_locations.mapped("id")):
                        _logger.info( s )
                        sjson = {
                            "warehouseId": s.location_id.id,
                            "warehouse": s.location_id.display_name,
                            "quantity": s.quantity,
                            "reserved": s.reserved_quantity,
                            "available": s.quantity - s.reserved_quantity
                        }
                        stocks.append(sjson)

            var["stocks"] = stocks

            result.append(var)

        if noti:
            logs = str(result)
            noti.stop_internal_notification(errors=errors,logs=logs)

        return result

    def street(self, contact, billing=False ):
        if not billing and "location_streetName" in contact:
            return contact["location_streetName"]+" "+contact["location_streetNumber"]
        else:
            return contact["billingInfo_streetName"]+" "+contact["billingInfo_streetNumber"]

    def city(self, contact, billing=False ):
        if not billing and "location_city" in contact:
            return contact["location_city"]
        else:
            return contact["billingInfo_city"]


    #return odoo country id
    def country(self, contact, billing=False ):
        #MercadoLibre country has no country? ok
        #take country from account company if not available
        country = False
        if not billing and "country" in contact and len(contact["country"]):
            country = contact["country"]
        else:
            country = ("billingInfo_country" in contact and contact["billingInfo_country"])
            #do something
        if country:
            countries = self.env["res.country"].search([("name","like",country)])
            if countries and len(countries):
                return countries[0].id

        company = self.company_id or self.env.user.company_id
        country = self.country_id or company.country_id

        return country.id

    def dstate(self, country, contact, billing=False ):
        full_state = ''

        #parse from MercadoLibre contact
        Receiver = {}
        Receiver.update(contact)
        if not billing:
            Receiver["state"] = { "name": ("location_state" in contact and contact["location_state"]) or "" }
        else:
            Receiver["state"] = { "name": ("billingInfo_state" in contact and contact["billingInfo_state"]) or "" }
        country_id = country

        state_id = False
        if (Receiver and 'state' in Receiver):
            if ('id' in Receiver['state']):
                state = self.env['res.country.state'].search([('code','like',Receiver['state']['id']),('country_id','=',country_id)])
                if (len(state)):
                    state_id = state[0].id
                    return state_id
                id_ml = Receiver['state']['id'].split("-")
                #_logger.info(Receiver)
                #_logger.info(id_ml)
                if (len(id_ml)==2):
                    id = id_ml[1]
                    state = self.env['res.country.state'].search([('code','like',id),('country_id','=',country_id)])
                    if (len(state)):
                        state_id = state[0].id
                        return state_id
            if ('name' in Receiver['state']):
                full_state = Receiver['state']['name']
                state = self.env['res.country.state'].search(['&',('name','like',full_state),('country_id','=',country_id)])
                if (len(state)):
                    state_id = state[0].id
        return state_id

    def full_phone(self, contact, billing=False ):
        return contact["phoneNumber"]

    def doc_info(self, contactfields):
        dinfo = {}
        if "billingInfo_docNumber" in contactfields and 'billingInfo_docType' in contactfields:

            doc_number = contactfields["billingInfo_docNumber"]
            doc_type = contactfields['billingInfo_docType']

            if (doc_type and ('afip.responsability.type' in self.env)):
                doctypeid = self.env['res.partner.id_category'].search([('code','=',doc_type)]).id
                if (doctypeid):
                    dinfo['main_id_category_id'] = doctypeid
                    dinfo['main_id_number'] = doc_number
                    if (doc_type=="CUIT"):
                        #IVA Responsable Inscripto
                        afipid = self.env['afip.responsability.type'].search([('code','=',1)]).id
                        dinfo["afip_responsability_type_id"] = afipid
                    else:
                        #if (Buyer['billing_info']['doc_type']=="DNI"):
                        #Consumidor Final
                        afipid = self.env['afip.responsability.type'].search([('code','=',5)]).id
                        dinfo["afip_responsability_type_id"] = afipid
                else:
                    _logger.error("res.partner.id_category:" + str(doc_type))
        return dinfo


    def rebind( self, meli_id, **post):
        res = ""
        _logger.info("rebind: "+str(meli_id)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id)
        if bp:
            bt = bp.binding_product_tmpl_id
            if bt:
                res = bt.product_template_rebind()
        return res

    def post_stock( self, meli_id, **post):
        _logger.info("post_stock: "+str(meli_id)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id)
        if bp:
            bt = bp.binding_product_tmpl_id
            if bt:
                res = bt.product_template_post_stock()
        return res

    def post_price( self, meli_id, **post):
        _logger.info("post_price: "+str(meli_id)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id)
        if bp:
            bt = bp.binding_product_tmpl_id
            if bt:
                res = bt.product_template_post_price()
        return res

    def post_stock_variant( self, meli_id, meli_id_variation, **post):
        _logger.info("post_stock: "+str(meli_id)+" meli_id_variation:"+str(meli_id_variation)+" post:"+str(post))
        bp = self.search_meli_binding_product(meli_id=meli_id,meli_id_variation=meli_id_variation)
        if bp:
            res = bp.product_post_stock()
        return res


    def import_sales( self, **post ):

        _logger.info("import_sales")
        account = self
        company = account.company_id or self.env.user.company_id
        noti = None
        logs = ""
        errors = ""

        #start notification
        try:
            internals = {
                "connection_account": self,
                "application_id": self.client_id or '',
                "user_id": self.seller_id or '',
                "topic": "sales",
                "resource": "import_sales",
                "state": "PROCESSING"
            }
            noti = self.env["mercadolibre.notification"].start_internal_notification( internals )
        except Exception as e:
            _logger.error("import_sales error creating notification: "+str(e))
            pass;

        result = []

        sales = post.get("sales")
        logs = str(sales)

        _logger.info("Processing sales")
        for sale in sales:
            res = self.import_sale( sale, noti )
            for r in res:
                result.append(r)

        #close notifications
        if noti:
            errors = str(result)
            logs = str(logs)
            noti.stop_internal_notification(errors=errors,logs=logs)

        _logger.info(result)
        return result

    def import_sale( self, sale, noti ):

        account = self
        company = account.company_id or self.env.user.company_id
        result = []
        pso = False
        psoid = False
        so = False

        _logger.info(sale)
        return result


    def import_products( self ):
        #

        return ""



    def import_product( self ):
        #

        return ""



    def import_image( self ):
        #

        return ""



    def import_shipment( self ):
        #

        return ""



    def import_payment( self ):
        #

        return ""
