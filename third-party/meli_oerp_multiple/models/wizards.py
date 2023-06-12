# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

from odoo import api, models, fields
import logging
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from .warning import warning
from datetime import datetime

_logger = logging.getLogger(__name__)

import base64

class product_template_update(models.TransientModel):
    _inherit = "mercadolibre.product.template.update"

    connection_account = fields.Many2one("mercadolibre.account",string="MercadoLibre Account")

    def product_template_update(self, context=None):
        context = context or self.env.context
        _logger.info("meli_oerp_multiple >> wizard product_template_update "+str(context))
        company = self.env.user.company_id
        product_ids = []
        if ('active_ids' in context):
            product_ids = context['active_ids']
        product_obj = self.env['product.template']

        warningobj = self.env['meli.warning']

        account = self.connection_account
        company = (account and account.company_id) or company

        if account:
            meli = self.env['meli.util'].get_new_instance( company, account )
            if meli.need_login():
                return meli.redirect_login()
        else:
            meli = None

        meli_id = False
        if self.meli_id:
            meli_id = self.meli_id
        res = {}
        for product_id in product_ids:
            product = product_obj.browse(product_id)
            if (product):
                if self.force_meli_pub:
                    product.meli_pub = True
                    for variant in product.product_variant_ids:
                        variant.meli_pub = True
                if (product.meli_pub):
                    res = product.product_template_update( meli_id=meli_id, meli=meli, account=account )

            if 'name' in res:
                return res

        return res

class ProductTemplateBindToMercadoLibre(models.TransientModel):

    _name = "mercadolibre.binder.wiz"
    _description = "Wizard de Product Template MercadoLibre Binder"
    _inherit = "ocapi.binder.wiz"

    connectors = fields.Many2many("mercadolibre.account", string='MercadoLibre Accounts',help="Cuenta de mercadolibre origen de la publicación")
    meli_id = fields.Char( string="MercadoLibre Products Ids",help="Ingresar uno o varios separados por coma: (MLXYYYYYYY: MLA123456789, MLA458..., ML...., ... )")
    bind_only = fields.Boolean( string="Bind only using SKU", help="Solo asociar producto y variantes usando SKU (No modifica el producto de Odoo)" )
    use_barcode = fields.Boolean( string="Use Barcode" )

    def product_template_add_to_connector(self, context=None):

        context = context or self.env.context

        _logger.info("product_template_add_to_connector (MercadoLibre)")

        company = self.env.user.company_id
        product_ids = context['active_ids']
        product_obj = self.env['product.template']

        res = {}
        for product_id in product_ids:

            product = product_obj.browse(product_id)

            for mercadolibre in self.connectors:
                meli_id = False
                bind_only = False
                _logger.info(_("Check %s in %s") % (product.display_name, mercadolibre.name))
                #Binding to
                if self.meli_id:
                    meli_id = self.meli_id.split(",")
                else:
                    meli_id = [False]
                if self.bind_only:
                    bind_only = self.bind_only
                for mid in meli_id:
                    product.mercadolibre_bind_to( mercadolibre, meli_id=mid, bind_variants=True, bind_only=bind_only )


    def product_template_remove_from_connector(self, context=None):

        context = context or self.env.context

        _logger.info("product_template_remove_from_connector (MercadoLibre)")

        company = self.env.user.company_id
        product_ids = context['active_ids']
        product_obj = self.env['product.template']

        res = {}
        for product_id in product_ids:

            product = product_obj.browse(product_id)

            for mercadolibre in self.connectors:
                _logger.info(_("Check %s in %s") % (product.display_name, mercadolibre.name))
                #Binding to
                meli_id = False
                if self.meli_id:
                    meli_id = self.meli_id.split(",")
                else:
                    meli_id = [False]
                for mid in meli_id:
                    product.mercadolibre_unbind_from( account=mercadolibre, meli_id=mid )

class ProductTemplateBindUpdate(models.TransientModel):

    _name = "mercadolibre.binder.update.wiz"
    _description = "Wizard de Product Template MercadoLibre Binder Update"

    update_odoo_product = fields.Boolean(string="Update Odoo Products")
    update_odoo_product_variants = fields.Boolean(string="Update Odoo Product Variants")
    update_images = fields.Boolean(string="Update images")
    update_stock = fields.Boolean(string="Only update stock")
    update_price = fields.Boolean(string="Only update price")

    def binding_product_template_update(self, context=None):

        context = context or self.env.context

        _logger.info("binding_product_template_update (MercadoLibre)")

        company = self.env.user.company_id
        bind_ids = ('active_ids' in context and context['active_ids']) or []
        bindobj = self.env['mercadolibre.product_template']

        res = {}

        for bind_id in bind_ids:

            bindT = bindobj.browse(bind_id)
            if bindT:
                bindT.product_template_update()


class ProductVariantBindUpdate(models.TransientModel):

    _name = "mercadolibre.binder.variant.update.wiz"
    _description = "Wizard de Product Variant MercadoLibre Binder Update"

    update_odoo_product = fields.Boolean(string="Update Full Odoo Product")
    #update_odoo_product_variants = fields.Boolean(string="Update Odoo Product Variants")
    #update_images = fields.Boolean(string="Update images")
    update_stock = fields.Boolean(string="Only update stock")
    update_price = fields.Boolean(string="Only update price")

    def binding_product_variant_update(self, context=None):

        context = context or self.env.context

        _logger.info("binding_product_variant_update (MercadoLibre)")

        warningobj = self.env['meli.warning']
        company = self.env.user.company_id
        bind_ids = ('active_ids' in context and context['active_ids']) or []
        bindobj = self.env['mercadolibre.product']

        rest = []
        correct = []

        for bind_id in bind_ids:

            bind = bindobj.browse(bind_id)
            if bind:
                if self.update_odoo_product:
                    res = bind.product_update()
                    if res and 'error' in res:
                        rest.append(res)
                    correct.append("Id: "+str(bind.conn_id)+" Product:"+str(bind.product_id.default_code))

                if self.update_price:
                    res = bind.product_post_price(context=context)
                    if res and 'error' in res:
                        rest.append(res)
                    correct.append("Id: "+str(bind.conn_id)+" Product:"+str(bind.product_id.default_code)+" Price:"+str(bind.price))

                if self.update_stock:
                    res = bind.product_post_stock(context=context)
                    if res and 'error' in res:
                        rest.append(res)
                    correct.append("Id: "+str(bind.conn_id)+" Product:"+str(bind.product_id.default_code)+" Stock:"+str(bind.stock))

        if len(rest):
            return warningobj.info( title='STOCK POST WARNING', message="Revisar publicaciones", message_html="<h3>Correct</h3>"+str(correct)+"<br/>"+"<h2>Errores</h2>"+str(rest), context = { "rjson": rest })

        return rest

class ProductVariantBindToMercadoLibre(models.TransientModel):

    _name = "mercadolibre.variant.binder.wiz"
    _description = "Wizard de Product Variant MercadoLibre Binder"
    _inherit = "ocapi.binder.wiz"

    connectors = fields.Many2many("mercadolibre.account", string='MercadoLibre Accounts')
    meli_id = fields.Char(string="MercadoLibre Product Id (MLXYYYYYYY: MLA123456789 )")
    meli_id_variation = fields.Char(string="MercadoLibre Product Variation Id ( ZZZZZZZZZ: 123456789 )")
    bind_only = fields.Boolean( string="Bind only using SKU", help="Solo asociar producto y variantes usando SKU (No modifica el producto de Odoo)" )

    def product_product_add_to_connector(self, context=None):

        context = context or self.env.context

        _logger.info("product_product_add_to_connector (MercadoLibre)")

        company = self.env.user.company_id
        product_ids = context['active_ids']
        product_obj = self.env['product.product']

        res = {}
        for product_id in product_ids:

            product = product_obj.browse(product_id)

            for mercadolibre in self.connectors:
                _logger.info(_("Check %s in %s") % (product.display_name, mercadolibre.name))
                meli_id = False
                meli_id_variation = False
                #Binding to
                if self.meli_id:
                    meli_id = self.meli_id

                if self.meli_id_variation:
                    meli_id_variation = self.meli_id_variation

                product.mercadolibre_bind_to( mercadolibre, meli_id=meli_id, meli_id_variation=meli_id_variation  )


    def product_product_remove_from_connector(self, context=None):

        context = context or self.env.context

        _logger.info("product_product_remove_from_connector (MercadoLibre)")

        company = self.env.user.company_id
        product_ids = context['active_ids']
        product_obj = self.env['product.product']

        res = {}
        for product_id in product_ids:

            product = product_obj.browse(product_id)

            for mercadolibre in self.connectors:
                _logger.info(_("Check %s in %s") % (product.display_name, mercadolibre.name))
                #Binding to
                meli_id = False
                meli_id_variation = False
                if self.meli_id:
                    meli_id = self.meli_id
                if self.meli_id_variation:
                    meli_id_variation = self.meli_id_variation
                product.mercadolibre_unbind_from( account=mercadolibre, meli_id=meli_id, meli_id_variation=meli_id_variation )

class ProductTemplatePostExtended(models.TransientModel):

    _inherit = "mercadolibre.product.template.post"

    force_meli_new_pub = fields.Boolean(string="Crear una nueva publicación")
    connectors = fields.Many2one("mercadolibre.account",string="MercadoLibre Account",required=True)
    force_meli_new_title = fields.Char(string="New Title")
    force_meli_new_price = fields.Float(string="New Price")
    force_meli_new_pricelist = fields.Many2one("product.pricelist",string="New Price List")

    def product_template_post(self, context=None):

        context = context or self.env.context
        company = self.env.user.company_id
        _logger.info("multiple product_template_post: context: " + str(context))

        product_ids = []
        if ('active_ids' in context):
            product_ids = context['active_ids']
        product_obj = self.env['product.template']
        warningobj = self.env['meli.warning']

        res = {}

        _logger.info("wizard > context in product_template_post:")
        _logger.info(self.env.context)
        custom_context = {
            'connectors': self.connectors,
            'force_meli_new_pub': self.force_meli_new_pub,

            'force_meli_pub': self.force_meli_pub,
            'force_meli_active': self.force_meli_active,

            'post_stock': self.post_stock,
            'post_price': self.post_price,

            'force_meli_new_title': self.force_meli_new_title,
            'force_meli_new_price': self.force_meli_new_price,
            'force_meli_new_pricelist': self.force_meli_new_pricelist,

        }
        posted_products = 0
        for product_id in product_ids:

            productT = product_obj.browse(product_id)

            for account in self.connectors:
                comp = account.company_id or company
                meli = self.env['meli.util'].get_new_instance( comp, account )
                if meli:
                    if meli.need_login():
                        return meli.redirect_login()
                    #res = productT.with_context(custom_context).product_template_post( context=None, account=account, meli=meli )

                    if (self.force_meli_pub and not productT.meli_pub):
                        productT.meli_pub = True
                    if (productT.meli_pub):

                        if self.post_stock:
                            res = productT.with_context(custom_context).product_template_post_stock(meli=meli,account=account)
                        if self.post_price:
                            res = productT.with_context(custom_context).product_template_post_price(meli=meli,account=account)
                        if not self.post_stock and not self.post_price:
                            res = productT.with_context(custom_context).product_template_post(context=None, account=account, meli=meli)

                    if res and 'name' in res:
                        return res
                    if (productT.meli_pub):
                        posted_products+=1

        if (posted_products==0 and not 'name' in res):
            res = warningobj.info( title='MELI WARNING', message="Se intentaron publicar 0 productos. Debe forzar las publicaciones o marcar el producto con el campo Meli Publication, debajo del titulo.", message_html="" )

        return res

class ProductTemplateBindingPostExtended(models.TransientModel):

    _name = "mercadolibre.product.template.binding.post"
    _inherit = "mercadolibre.product.template.post"
    _description = "Mercadolibre Product Template Binding"

    def product_template_post(self, context=None):

        context = context or self.env.context
        company = self.env.user.company_id
        _logger.info("multiple product_template_post: context: " + str(context))

        product_bindT_ids = []
        if ('active_ids' in context):
            product_bindT_ids = context['active_ids']
        product_bindT_obj = self.env['mercadolibre.product_template']
        warningobj = self.env['meli.warning']

        res = {}

        _logger.info("wizard > context in product_template_post:")
        _logger.info(self.env.context)
        custom_context = {
            'connectors': self.connectors,
            'force_meli_new_pub': self.force_meli_new_pub,

            'force_meli_pub': self.force_meli_pub,
            'force_meli_active': self.force_meli_active,

            'post_stock': self.post_stock,
            'post_price': self.post_price,

            'force_meli_new_title': self.force_meli_new_title,
            'force_meli_new_price': self.force_meli_new_price,
            'force_meli_new_pricelist': self.force_meli_new_pricelist,

        }
        posted_products = 0
        connectors = self.connectors and self.connectors.ids or []
        for product_bindT_id in product_bindT_ids:

            product_bindT = product_bindT_obj.browse(product_bindT_id)
            account = product_bindT.connection_account
            if account.id in connectors:

                comp = account.company_id or company
                meli = self.env['meli.util'].get_new_instance( comp, account )

                if meli:
                    if meli.need_login():
                        return meli.redirect_login()
                    #res = productT.with_context(custom_context).product_template_post( context=None, account=account, meli=meli )

                    if (self.force_meli_pub and not product_bindT.meli_pub):
                        product_bindT.meli_pub = True

                    if (product_bindT.meli_pub):

                        if self.post_stock:
                            res = product_bindT.with_context(custom_context).product_template_post_stock(meli=meli,account=account)
                        if self.post_price:
                            res = product_bindT.with_context(custom_context).product_template_post_price(meli=meli,account=account)
                        if not self.post_stock and not self.post_price:
                            res = product_bindT.with_context(custom_context).product_template_post(context=None, account=account, meli=meli)

                    if res and 'name' in res:
                        return res

                    if (product_bindT.meli_pub):
                        posted_products+=1

        if (posted_products==0 and not 'name' in res):
            res = warningobj.info( title='MELI WARNING', message="Se intentaron publicar 0 productos. Debe forzar las publicaciones o marcar el producto con el campo Meli Publication, debajo del titulo.", message_html="" )

        return res


class NotificationsProcessWiz(models.TransientModel):
    _name = "mercadolibre.notification.wiz"
    _description = "MercadoLibre Notifications Wiz"

    connection_account = fields.Many2one( "mercadolibre.account", string='MercadoLibre Account',help="Cuenta de mercadolibre origen de la publicación")
    reprocess_force = fields.Boolean(string="Reprocess",default=False)
    def process_notifications( self, context=None ):

        context = context or self.env.context

        _logger.info("process_notifications (MercadoLibre)")
        noti_ids = ('active_ids' in context and context['active_ids']) or []
        noti_obj = self.env['mercadolibre.notification']

        custom_context = {
            'connection_account': self.connection_account,
            'reprocess_force': self.reprocess_force,
        }

        try:
            meli = None
            if self.connection_account:
                meli = self.env['meli.util'].get_new_instance( self.connection_account.company_id, self.connection_account )
                if meli.need_login():
                    return meli.redirect_login()

            ##if not self.connection_account:
            #    raise UserError('Connection Account not defined!')
            for noti_id in noti_ids:

                _logger.info("Processing notification: %s " % (noti_id) )

                noti = noti_obj.browse(noti_id)
                ret = []
                if noti:
                    reti = None
                    if self.connection_account and noti.connection_account and noti.connection_account.id==self.connection_account.id:
                        reti = noti.with_context(custom_context).process_notification(meli=meli)
                    else:
                        reti = noti.with_context(custom_context).process_notification()
                    if reti:
                        ret.append(str(reti))

        except Exception as e:
            _logger.info("process_notifications > Error procesando notificacion")
            _logger.error(e, exc_info=True)
            _logger.error(str(ret))
            #self._cr.rollback()
            raise e

        _logger.info("Processing notification result: %s " % (str(ret)) )


#class SaleOrderGlobalInvoice(models.TransientModel):
#
#    _name = "sale.order.global.invoice.meli.wiz"
#    _description = "Wizard de Factura Global"


class product_template_import(models.TransientModel):

    _inherit = "mercadolibre.product.template.import"


    def create_full_report( self, context=None, config=None, meli=None):
        _logger.info("Creating full report")
        context = context or self.env.context
        company = self.env.user.company_id
        account_ids = ('active_ids' in context and context['active_ids']) or []
        #product_obj = self.env['product.template']
        account = self.env['mercadolibre.account'].browse(account_ids)
        odoo_meli_ids = account.list_meli_ids()

        _logger.info("product_template_import context:"+str(context))

        warningobj = self.env['meli.warning']

        if not account:
            return warningobj.error(title="No account defined")
            
        company = (account and account.company_id) or company
        meli = self.env['meli.util'].get_new_instance(company, account )
        if meli.need_login():
            return meli.redirect_login()
            
        csv_report_header = ""
        csv_report = ""
        csv_report_di = []
        
        # meli_id / #variations / meli sku / meli_price / meli_stock -  import status (missing, duplicate, sync) / price to pub / stock to pub  / price status / stock status
        
        #LIST FIRST active publications and see if they are in the database
        #LIST SECOND paused publications and see if they are in the database
        #LIST OTHER STATES
        ### ACTIVE AND PAUSED
        meli_id = None
        
        post_state_filter = { 'status': 'active' }
        fetched_meli_ids_active = account.fetch_list_meli_ids( params=post_state_filter )
        actives_total = len(fetched_meli_ids_active)

        post_state_filter = { 'status': 'paused' }
        fetched_meli_ids_paused = account.fetch_list_meli_ids( params=post_state_filter )
        paused_total = len(fetched_meli_ids_paused)

        ### ACTIVE
        actives_to_sync = []
        co = 0
        for mli in fetched_meli_ids_active:
            co+=1
            mli_rec = {'meli_sku': '', 'meli_id': mli, 'meli_status': 'active', 'imp_status': 'synced' }
            #fetchm = meli.get("/items/"+mli, { 'access_token': meli.access_token } )
            rjson = account.fetch_meli_product( meli_id = mli, meli=meli )
            if rjson:                
                mli_rec["meli_sku"] = account.fetch_meli_sku( meli_id = mli, meli=meli, rjson=rjson )
                mli_rec["meli_variations"] = ( "variations" in rjson and rjson["variations"] and len(rjson["variations"]) ) or 1
                mli_rec["odoo_binds"] =  '0'

                mli_rec["meli_price"] = rjson["price"]
                mli_rec["odoo_price"] =  ''
                
                mli_rec["meli_qty"] = rjson["available_quantity"]
                mli_rec["odoo_stock"] =  ''
                
            if mli not in odoo_meli_ids:
                actives_to_sync.append(mli)
                mli_rec['imp_status'] = 'missing'
            else:
                ml_bind_product_id = account.search_meli_binding_product( meli_id = mli )
                if ml_bind_product_id:
                    binds = (len(ml_bind_product_id))
                    if ( int(binds) != int(mli_rec["meli_variations"]) ):
                        ml_bind_product_id[0].binding_product_tmpl_id.product_template_rebind()
                        ml_bind_product_id = account.search_meli_binding_product( meli_id = mli )
                        binds = (len(ml_bind_product_id))
                        
                    mli_rec["odoo_binds"] =  binds
                    #ml_bind_product_id[0].update_price()
                    mli_rec["odoo_price"] = ml_bind_product_id[0].meli_price
                    mli_rec["odoo_stock"] = ml_bind_product_id.mapped('stock')

                               
            csv_report_di.append(mli_rec)
            if co==40:
                co = 0
                #_logger.info(len(csv_report_di)+str("/")+str(actives_total+paused_total))

        ### PAUSED        
        paused_to_sync = []
        co = 0
        for mli in fetched_meli_ids_paused:
            co+=1
            mli_rec = {'meli_sku': '', 'meli_id': mli, 'meli_status': 'paused', 'imp_status': 'synced' }
            #fetchm = meli.get("/items/"+mli, { 'access_token': meli.access_token })
            rjson = account.fetch_meli_product( meli_id = mli, meli=meli )
            if rjson and "id" in rjson:
                mli_rec["meli_sku"] = account.fetch_meli_sku( meli_id = mli, meli=meli, rjson=rjson )
                mli_rec["meli_variations"] = ( "variations" in rjson and rjson["variations"] and len(rjson["variations"]) ) or 1
                mli_rec["odoo_binds"] =  '0'

                mli_rec["meli_price"] = ("price" in rjson and rjson["price"]) or ""
                mli_rec["odoo_price"] =  ''
                
                mli_rec["meli_qty"] = ("available_quantity" in rjson and rjson["available_quantity"]) or ""
                mli_rec["odoo_stock"] =  ''
                
            if mli not in odoo_meli_ids:
                paused_to_sync.append(mli)
                mli_rec['imp_status'] = 'missing'
            else:
                ml_bind_product_id = account.search_meli_binding_product( meli_id = mli )
                if ml_bind_product_id:
                    binds = (len(ml_bind_product_id))
                    if ( int(binds) != int(mli_rec["meli_variations"]) ):
                        ml_bind_product_id[0].binding_product_tmpl_id.product_template_rebind()
                        ml_bind_product_id = account.search_meli_binding_product( meli_id = mli )
                        binds = (len(ml_bind_product_id))
                        
                    mli_rec["odoo_binds"] =  binds
                    #ml_bind_product_id[0].update_price()
                    mli_rec["odoo_price"] = ml_bind_product_id[0].meli_price
                    mli_rec["odoo_stock"] = ml_bind_product_id.mapped('stock')
                    
                
            csv_report_di.append(mli_rec)
            if co==40:
                co = 0
                #_logger.info(len(csv_report_di)+str("/")+str(actives_total+paused_total))
            
        sep = ""
        if (len(csv_report_di)):
            for field in csv_report_di[0]:
                csv_report_header+= sep+str(field)                
                sep = ";"
            csv_report+= csv_report_header+"\n"

            for sync in csv_report_di:
                sep = ""
                for field in sync:
                    csv_report+= sep+'"'+str(sync[field])+'"'
                    sep = ";"
                csv_report+= "\n"            

        
        #csv_report_attachment_last = self.env["ir.attachment"].search([('res_id','=',self.id)], order='id desc', limit=1 )
        #if (csv_report_attachment_last):
        #    csv_report_last = csv_report_attachment_last.index_content
        #    csv_report = csv_report_last+"\n"+csv_report
        #else:
        #    csv_report = csv_report_header+"\n"+csv_report
        #_logger.info(csv_report)
        csv_report_encoded = csv_report.encode()
        b64_csv = base64.b64encode(csv_report_encoded)
        ATTACHMENT_NAME = "FullMassiveReport"

        csv_report_attachment = self.env['ir.attachment'].create({
            'name': ATTACHMENT_NAME+'.csv',
            'type': 'binary',
            'datas': b64_csv,
            #'datas_fname': ATTACHMENT_NAME + '.csv',
            'access_token': self.env['ir.attachment']._generate_access_token(),
            #'store_fname': ATTACHMENT_NAME+'.csv',
            'res_model': 'mercadolibre.product.template.import',
            'res_id': self.id,
            'mimetype': 'text/csv'
        })

        csv_report_attachment_link= ''
        if csv_report_attachment:
            self.report_import = csv_report_attachment.id
            csv_report_attachment_link = "/web/content/"+str(csv_report_attachment.id)+"?download=true&access_token="+str(csv_report_attachment.access_token)
            self.report_import_link = csv_report_attachment_link
            #<a class="fa fa-download" t-attf-title="Download Attachment {{asset.name}}" t-attf-href="/web/content/#{asset.attachment.id}?download=true&amp;access_token=#{asset.attachment.access_token}" target="_blank"></a>
            _logger.info("Creating full report OK!")
            return warningobj.info(title='Creating full report OK!', message=""+str(csv_report_attachment_link), message_html='<a href="'+str(csv_report_attachment_link)+'" target="_blank">Descargar reporte competo en CSV</a>')
            

        
            
        _logger.error("Creating full report failed: "+str(csv_report_encoded))
        return {
        #    "type": "set_scrollTop",
                    
        }


    def check_sync_status( self, context=None, config=None, meli=None ):
        context = context or self.env.context
        _logger.info("check_sync_status:"+str(context))
        company = self.env.user.company_id

        account_ids = ('active_ids' in context and context['active_ids']) or []
        account = self.env['mercadolibre.account'].browse(account_ids)
        odoo_meli_ids = account.list_meli_ids()
        _logger.info("odoo_meli_ids: ###" + str(len(odoo_meli_ids)) )

        config = config or (account and account.configuration) or company
        seller_id = account and account.seller_id
        #product_obj = self.env['product.product']
        #meli_ids = product_obj.search([('meli_id','!=',False)]).mapped('meli_id')
        #_logger.info("meli_ids:"+str(meli_ids))

        company = (account and account.company_id) or company
        meli = self.env['meli.util'].get_new_instance(company, account )
        if meli.need_login():
            return meli.redirect_login()

        results = []
        post_state_filter = {}

        meli_id = self.meli_id

        ### ACTIVE
        post_state_filter = { 'status': 'active' }
        if meli_id:
            post_state_filter.update( { 'meli_id': meli_id } )

        fetched_meli_ids_active = account.fetch_list_meli_ids( params=post_state_filter )
        actives_total = len(fetched_meli_ids_active)

        actives_to_sync = []
        for mli in fetched_meli_ids_active:
            if mli not in odoo_meli_ids:
                actives_to_sync.append(mli)

        ### PAUSED
        post_state_filter = { 'status': 'paused' }
        if meli_id:
            post_state_filter.update( { 'meli_id': meli_id } )

        fetched_meli_ids_paused = account.fetch_list_meli_ids( params=post_state_filter )
        paused_total = len(fetched_meli_ids_paused)

        paused_to_sync = []
        for mli in fetched_meli_ids_paused:
            if mli not in odoo_meli_ids:
                paused_to_sync.append(mli)



        ### CLOSED
        post_state_filter = { 'status': 'closed' }
        if meli_id:
            post_state_filter.update( { 'meli_id': meli_id } )

        fetched_meli_ids_closed = account.fetch_list_meli_ids( params=post_state_filter )
        closed_total = len(fetched_meli_ids_closed)

        closed_to_sync = []
        for mli in fetched_meli_ids_closed:
            if mli not in odoo_meli_ids:
                closed_to_sync.append(mli)


        #check last import Status
        attachments = self.env["ir.attachment"].search([('res_id','=',self.id)], order='id desc')
        last_attachment = None
        report_import_link = ""
        if attachments:
            last_attachment = attachments[0]
            report_import_link = "/web/content/"+str(last_attachment.id)+"?download=true&access_token="+str(last_attachment.access_token)


        result =  {
            'actives_to_sync': str(len(actives_to_sync))+" / "+str(actives_total),
            'paused_to_sync': str(len(paused_to_sync))+" / "+str(paused_total),
            'closed_to_sync': str(len(closed_to_sync))+" / "+str(closed_total),
        }

        result.update({'report_import': last_attachment})
        result.update({'report_import_link': report_import_link})

        _logger.info(result)
        return result

    def product_template_import(self, context=None):

        context = context or self.env.context
        company = self.env.user.company_id
        account_ids = ('active_ids' in context and context['active_ids']) or []
        #product_obj = self.env['product.template']
        account = self.env['mercadolibre.account'].browse(account_ids)

        _logger.info("product_template_import context:"+str(context))

        warningobj = self.env['meli.warning']

        if not account:
            return warningobj.error(title="No account defined")

        company = (account and account.company_id) or company
        meli = self.env['meli.util'].get_new_instance(company, account )
        if meli.need_login():
            return meli.redirect_login()

        custom_context = {
            "post_state": self.post_state,
            "meli_id": self.meli_id,
            "force_meli_pub": self.force_meli_pub,
            "force_create_variants": self.force_create_variants,
            "force_dont_create": self.force_dont_create,
            "force_meli_website_published": self.force_meli_website_published,
            "force_meli_website_category_create_and_assign": self.force_meli_website_category_create_and_assign,
            "batch_processing_unit": self.batch_processing_unit,
            "batch_processing_unit_offset": self.batch_processing_unit_offset,
            "batch_actives_to_sync": self.batch_actives_to_sync,
            "batch_paused_to_sync": self.batch_paused_to_sync,
        }

        _logger.info("product_template_import custom_context:"+str(custom_context)+" account:"+str(account and account.name))

        meli_id = False
        if self.meli_id:
            meli_id = self.meli_id

        res = {}
        if account:
            res = account.product_meli_get_products(context=custom_context)

        _logger.info("import res:"+str(res))
        if res and "json_report" in res:
            if "paging" in res:
                if "next_offset" in res["paging"]:
                    self.batch_processing_unit_offset = res["paging"]["next_offset"]

            #update batch_processing_unit_offset
            json_report = res["json_report"]
            full_report = json_report["synced"]+json_report["missing"]+json_report["duplicates"]
            csv_report_header = ""
            csv_report = ""            

            if full_report:
                sep = ""
                for field in full_report[0]:
                    csv_report_header+= sep+str(field)
                    sep = ";"

                for sync in full_report:
                    sep = ""
                    for field in sync:
                        csv_report+= sep+'"'+str(sync[field])+'"'
                        sep = ";"
                    csv_report+= "\n"

            csv_report_attachment_last = self.env["ir.attachment"].search([('res_id','=',self.id)], order='id desc', limit=1 )
            if (csv_report_attachment_last):
                csv_report_last = csv_report_attachment_last.index_content
                csv_report = csv_report_last+"\n"+csv_report
            else:
                csv_report = csv_report_header+"\n"+csv_report
            #_logger.info(csv_report)
            b64_csv = base64.b64encode(csv_report.encode())
            now = datetime.now()
            ATTACHMENT_NAME = "MassiveImport-"+str(account and account.name)+"-"+str(now.strftime("%Y-%m-%d, %H:%M"))

            csv_report_attachment = self.env['ir.attachment'].create({
                'name': ATTACHMENT_NAME+'.csv',
                'type': 'binary',
                'datas': b64_csv,
                #'datas_fname': ATTACHMENT_NAME + '.csv',
                'access_token': self.env['ir.attachment']._generate_access_token(),
                #'store_fname': ATTACHMENT_NAME+'.csv',
                'res_model': 'mercadolibre.product.template.import',
                'res_id': self.id,
                'mimetype': 'text/csv'
            })

            csv_report_attachment_link= ''
            if csv_report_attachment:
                self.report_import = csv_report_attachment.id
                csv_report_attachment_link = "/web/content/"+str(csv_report_attachment.id)+"?download=true&access_token="+str(csv_report_attachment.access_token)
                self.report_import_link = csv_report_attachment_link
                #<a class="fa fa-download" t-attf-title="Download Attachment {{asset.name}}" t-attf-href="/web/content/#{asset.attachment.id}?download=true&amp;access_token=#{asset.attachment.access_token}" target="_blank"></a>

            res.update({'csv_report':  csv_report, 'csv_report_attachment':  csv_report_attachment, 'csv_report_attachment_link': csv_report_attachment_link })

            _logger.info('Processing import status ' + str(self.import_status)+ " report_import:"+str(self.report_import))
            res = self.show_import_wizard()
        return res


        
        
