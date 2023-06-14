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
import logging
import re

import json

import logging
_logger = logging.getLogger(__name__)

from dateutil.parser import *
from datetime import *
from urllib.request import urlopen
import requests
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode


import base64
from odoo.addons.meli_oerp.models.versions import *
from odoo.addons.meli_oerp_accounting.models.versions import *

#https://developers.mercadolibre.com.co/es_ar/cargar-factura

#curl -X POST https://api.mercadolibre.com/packs/$PACK_ID/fiscal_documents?access_token=$ACCESS_TOKEN
#-H 'Content-Type: multipart/form-data' \
#-F 'fiscal_document=@/home/user/.../Factura_adjunta.pdf'

#curl -X POST https://api.mercadolibre.com/packs/$PACK_ID/fiscal_documents?access_token=$ACCESS_TOKEN
#  -H 'content-type: multipart/form-data;'
#  -F 'fiscal_document=@/home/user/.../Factura_adjunta.pdf'
#  -F 'fiscal_document=@/home/user/.../Factura_adjunta.xml'

#https://api.mercadolibre.com/packs/2000001921401367/fiscal_documents?access_token=APP_USR-6630319130713446-021014-a71d1e5701c937af631cabdb0bf0c5c3-115266467#json

"""
							<button name='orders_post_invoice' type="object"
								string="Publicar Facturas"
								attrs="{'invisible':[('invoice_posted','=',True)]}"
								class="oe_stat_button"
								icon="fa-globe"/>
							<field name="invoice_posted"/>
							<field name="invoice_fiscal_documents"/>
"""

class Invoice(models.Model):

    _inherit = acc_inv_model

    #@api.multi
    def firmar_factura_electronica(self):
        _logger.info("meli_oerp: firmar_factura_electronica")
        try:
            for inv in self:
                res = super( Invoice, inv ).firmar_factura_electronica()
                origin = "origin" in inv._fields and inv.origin
                origin = "invoice_origin" in inv._fields and inv.invoice_origin
                sorder = self.env['sale.order'].search([('name','=',origin)], limit=1)
                if sorder:
                    if sorder and sorder.meli_orders:
                        sorder.meli_orders[0].orders_post_invoice()

        except Exception as e:
            raise e;


    def crear_facturas( self ):
        #
        _logger.info("Crear Facturas")

        XMLname = None
        XMLbytes = None

        PDFName = None
        PDFbytes = None
        #zip_content = BytesIO()
        #zip_content.write(base64.b64decode(self.attachment_file))

        #zip_file.writestr(, zip_content.getvalue())

        #XMLbytes = base64.b64decode(self.attachment_file)

        template = self.env.ref(report_invoices)
        if (report_invoices_name):
            #template = self.env["ir.actions.report"].search(('report_name','=ilike',''+str(report_invoices_name)))
            _logger.info("report_invoices_name:"+str(report_invoices_name)+" founded in ir.actions.report > "+str(template))
        if (report_invoices_id):
            template = self.env["ir.actions.report"].browse(report_invoices_id)
            _logger.info("report_invoices_id: "+str(report_invoices_id)+" founded in ir.actions.report > "+str(template))


        try:
            if self.env.ref('l10n_co_cei.account_invoices_fe'):

                if "attachment_file" in self._fields:
                    XMLbytes = self.attachment_file
                    XMLname = self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.xml'
                    PDFName = self.filename.replace('fv', 'ad').replace('nc', 'ad').replace('nd', 'ad') + '.pdf'
                    #_logger.info(XMLbytes)
                    _logger.info(XMLname)

                template = self.env.ref('l10n_co_cei.account_invoices_fe')
        except:
            pass;

        if (template):

            render_template = report_render( template, res_ids=[self.id])

            #_logger.info(render_template)
            #PDFbytes = base64.b64decode(base64.b64encode(render_template[0]))

            if not PDFbytes:
                PDFbytes = base64.b64encode(render_template[0])

            if not PDFName:
                PDFName = re.sub(r'\W+', '', self.name or self.number) + '.pdf'

            if ( 'sii_xml_dte' in self.env[acc_inv_model]._fields and self.sii_xml_dte ):
                #XMLbytes = base64.b64encode( bytes(self.sii_xml_dte, "ascii") )
                XMLbytes = base64.b64encode( bytes(self.sii_xml_dte, 'utf-8') )
                XMLname = re.sub( r'\W+', '', self.name or self.number ) + '.xml'

            #_logger.info(PDFbytes)
            _logger.info(PDFName)
            _logger.info(XMLname)

        return XMLname, XMLbytes, PDFName, PDFbytes

class OrdersInvoice(models.Model):

    _inherit = "mercadolibre.orders"

    invoice_pdf = fields.Binary(string='Invoice PDF')
    invoice_pdf_filename = fields.Char(string="PDF Filename")
    invoice_xml = fields.Binary(string='Invoice XML')
    invoice_xml_filename = fields.Char(string="XML Filename")

    invoice_fiscal_documents = fields.Char(string='Invoice Fiscal Documents',index=True)
    invoice_created = fields.Boolean(string='Invoice Created',index=True)
    invoice_posted = fields.Boolean(string='Invoice Posted',index=True)

    invoice_type = fields.Selection(string="Tipo de factura", selection=[('unknown','Indefinido'),('ticket','Boleta'),('invoice','Factura')],default='unknown',index=True)

    def orders_create_invoice(self, context=None, meli=None, config=None):
        _logger.info("orders_create_invoice:"+str(context))
        self.invoice_created = True
        so = self and self.sale_order
        config = config or ("connection_account" in self._fields and self.connection_account and self.connection_account.configuration)
        config = config or so.company_id or self.env.user.company_id
        if (so):
            so.meli_create_invoice( meli=meli, config=config )


    def orders_post_invoice(self, context=None, meli=None, config=None):
        context = context or self.env.context
        _logger.info("orders_post_invoice: context: "+str(context))

        self.invoice_posted = False

        _logger.info("Create binary PDF and XML for attach files")

        config = config or ("connection_account" in self._fields and self.connection_account and self.connection_account.configuration)
        company = (config and 'company_id' in config._fields and config.company_id)

        so = self.sale_order
        if so:
            config = config or so.company_id or self.env.user.company_id
            if not meli:
                if ("connection_account" in self._fields and self.connection_account):
                    account = self.connection_account
                    meli = self.env['meli.util'].get_new_instance(config, account)
                else:
                    meli = self.env['meli.util'].get_new_instance(config)

            invoices = self.env[acc_inv_model].search([(invoice_origin,'=',so.name)])
            #'estado_validacion': record['fe_approved'],
            respost = ""
            for inv in invoices:
                #chequear inv validacion
                #estado_dian = fields.Text(
                #    related="envio_fe_id.respuesta_validacion",
                #    copy=False
                #)
                files = []

                if ('estado_dian' in inv._fields and ( inv.estado_dian and 'Procesado Correctamente' in inv.estado_dian) and inv.zipped_file):
                    _logger.info("Factura validada, generando.... para envio.")

                    XMLname, XMLbytes, PDFName, PDFbytes = inv.crear_facturas()

                    if PDFbytes:

                        self.invoice_pdf = PDFbytes
                        self.invoice_pdf_filename = PDFName
                    if XMLbytes:
                        self.invoice_xml = XMLbytes
                        self.invoice_xml_filename = XMLname
                else:
                    XMLname, XMLbytes, PDFName, PDFbytes = inv.crear_facturas()

                    if PDFbytes:
                        self.invoice_pdf = PDFbytes
                        self.invoice_pdf_filename = PDFName
                    if XMLbytes:
                        self.invoice_xml = XMLbytes
                        self.invoice_xml_filename = XMLname

                if PDFName and PDFbytes and XMLname and XMLbytes:
                    files = [ ('fiscal_document', ( PDFName, base64.b64decode(PDFbytes), 'application/pdf')),
                              ('fiscal_document', ( XMLname, base64.b64decode(XMLbytes), 'application/xml')) ]
                elif PDFName and PDFbytes:
                    files = [ ('fiscal_document', ( PDFName, base64.b64decode(PDFbytes), 'application/pdf'))]
                elif XMLname and XMLbytes:
                    files = [ ('fiscal_document', ( XMLName, base64.b64decode(XMLbytes), 'application/xml'))]

                    #files = [ ('fiscal_document', ( PDFName, base64.b64decode(PDFbytes), 'application/pdf')) ]
                    #files = [ ('fiscal_document', ( XMLname, base64.b64decode(XMLbytes), 'application/xml') ]

                do_not_send = ("mercadolibre_post_invoice_dont_send" in config._fields and config.mercadolibre_post_invoice_dont_send)

                if meli and files and ( do_not_send == False ):
                    res = meli.uploadfiles("/packs/"+str(self.pack_id or self.order_id)+"/fiscal_documents", files=files, params={ "access_token": meli.access_token } )
                    _logger.info(res)
                    if res:
                        _logger.info(res.json())
                        respost += str(res.json())
                        #{'statusCode': 409, 'code': 'conflict', 'message': 'File Not allowed, the max amount of files already exist for the pack: 4433064137 and seller: 115266467', 'requestId': '557c88de-160f-4de9-a36d-2c01cb277ec6'}
                        if 'error' in res.json():
                            _logger.error(res.json())
                            self.invoice_posted = False
                            self.invoice_fiscal_documents = respost
                            return res
                    self.invoice_posted = True

            self.invoice_fiscal_documents = respost
            self.invoice_type = ("boleta" in respost and "ticket") or ("factura" in respost and "invoice") or "unknown"


        #self.invoice_posted = False


    def orders_get_invoice(self, context=None, meli=None, config=None):
        _logger.info("orders_get_invoice")

        context = context or self.env.context
        _logger.info("orders_get_invoice: context: "+str(context))

        self.invoice_fiscal_documents = ""

        config = config or ("connection_account" in self._fields and self.connection_account and self.connection_account.configuration)
        company = (config and 'company_id' in config._fields and config.company_id)

        so = self.sale_order
        if so:
            config = config or so.company_id or self.env.user.company_id
            if not meli:
                if ("connection_account" in self._fields and self.connection_account):
                    account = self.connection_account
                    meli = self.env['meli.util'].get_new_instance(config, account)
                else:
                    meli = self.env['meli.util'].get_new_instance(config)

            #xxxx
            #res = meli.uploadfiles("/packs/"+str(self.pack_id or self.order_id)+"/fiscal_documents", files=files, params={ "access_token": meli.access_token } )
            respost = ""
            res = meli.get("/packs/"+str(self.pack_id or self.order_id)+"/fiscal_documents", params={ "access_token": meli.access_token } )
            if res:
                _logger.info(res.json())
                respost += str(res.json())

                if 'error' in res.json():
                    _logger.error(res.json())
                    self.invoice_posted = False
                    self.invoice_fiscal_documents = respost
                    return res

            self.invoice_posted = True
            self.invoice_fiscal_documents = respost
            self.invoice_type = ("boleta" in respost and "ticket") or ("factura" in respost and "invoice") or "unknown"


