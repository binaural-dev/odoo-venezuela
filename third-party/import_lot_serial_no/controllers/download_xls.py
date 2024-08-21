# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import content_disposition
import base64


class Download_xls(http.Controller):

    @http.route('/web/binary/download_document', type='http', auth="public")
    def download_document(self, model, id, **kw):

        Model = request.env[model]
        res = Model.browse(int(id)).sudo()

        if res.sample_option == 'lot':

            invoice_xls = request.env['ir.attachment'].sudo().search([('name', '=', 'lot.xlsx')])
            filecontent = invoice_xls.datas
            filename = 'Lot.xls'
            filecontent = base64.b64decode(filecontent)

        elif res.sample_option == 'lot_serial':

            invoice_xls = request.env['ir.attachment'].sudo().search([('name', '=', 'lot_serial.xlsx')])
            filecontent = invoice_xls.datas
            filename = 'Lot Serial.xls'
            filecontent = base64.b64decode(filecontent)

        return request.make_response(filecontent,
                                     [('Content-Type', 'application/octet-stream'),
                                      ('Content-Disposition', content_disposition(filename))])
