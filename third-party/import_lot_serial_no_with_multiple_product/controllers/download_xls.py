# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import content_disposition
import base64
import os, os.path
import csv
from os import listdir
import sys

class Download_xls(http.Controller):
    
    @http.route('/web/binary/download_document1', type='http', auth="public")
    def download_document(self,model,id, **kw):

        Model = request.env[model]
        res = Model.browse(int(id)).sudo()


        if model == 'import.lot.multi.wizard':
            if res.sample_option == 'xls' and res.select_lot == 'serial':
                invoice_xls = request.env['ir.attachment'].sudo().search([('name','=','Import_mass_lot_serial.xls')])
                filecontent = invoice_xls.datas
                filename = 'Import_mass_lot_serial.xls'
                filecontent = base64.b64decode(filecontent)
    
            elif res.sample_option == 'csv' and res.select_lot == 'serial':
                invoice_xls = request.env['ir.attachment'].sudo().search([('name','=','Import_mass_lot_serial.csv')])
                filecontent = invoice_xls.datas
                filename = 'Import_mass_lot_serial.csv'
                filecontent = base64.b64decode(filecontent)
                
            elif res.sample_option == 'xls' and res.select_lot == 'lot':
                invoice_xls = request.env['ir.attachment'].sudo().search([('name','=','Import_mass_lot.xls')])
                filecontent = invoice_xls.datas
                filename = 'Import_mass_lot.xls'
                filecontent = base64.b64decode(filecontent)
    
            elif res.sample_option == 'csv' and res.select_lot == 'lot':
                invoice_xls = request.env['ir.attachment'].sudo().search([('name','=','Import_mass_lot.csv')])
                filecontent = invoice_xls.datas
                filename = 'Import_mass_lot.csv'
                filecontent = base64.b64decode(filecontent)
                
                
    
            return request.make_response(filecontent,
                [('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', content_disposition(filename))])
            
            
        return True