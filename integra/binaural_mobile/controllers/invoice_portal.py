import logging
import json

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.account.controllers.portal import PortalAccount
# from .common_routes import brand
from . import utils

_logger = logging.getLogger(__name__)

class PortalAccount(PortalAccount):
    @http.route(['/my/invoices', '/my/invoices/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_invoices(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        res = super(PortalAccount, self).portal_my_invoices(page=page, date_begin=date_begin, date_end=date_end, sortby=sortby, filterby=filterby, **kw)
        if request.env.user.employee_id.is_seller:
            user_id = request.env.user.id
            domain = [('invoice_user_id', '=', user_id)]
            invoices_count = request.env['account.move'].search_count(domain)
            pager = request.website.pager(
                url="/my/invoices",
                url_args={'date_begin': date_begin, 'date_end': date_end},
                total=invoices_count,
                page=page,
                step=self._items_per_page
            )

            AccountInvoice = request.env['account.move']
            invoices = AccountInvoice.sudo().search(domain, order='date desc', limit=self._items_per_page, offset=pager['offset'])
            request.session['my_invoices_history'] = invoices.ids[:100]
            is_seller = True
            res.qcontext.update({
                'invoices': invoices,
                'pager': pager,
                'default_url': '/my/invoices',
                "is_seller": is_seller,
            })
        return res
    
    @http.route('/my/invoices/<int:invoice_id>/seller_invoice', type='http', auth="public", website=True)
    def portal_my_invoice_seller(self, invoice_id=None, access_token=None, **kw):
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        states = invoice._fields['payment_state'].selection
        payment_state = invoice.payment_state

        for state in states:
            if state[0] == payment_state:
                payment_state = state[1]
                break

        return request.render('binaural_mobile.portal_invoices_seller', {
            'invoice': invoice,
            'payment_state': payment_state,
        })
    

    
    