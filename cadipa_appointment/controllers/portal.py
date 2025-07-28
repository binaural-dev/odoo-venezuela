import logging

from odoo import _, http, fields
from odoo.http import request, route
from odoo.osv import expression
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.account.controllers.portal import PortalAccount
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
from odoo.tools import date_utils

_logger = logging.getLogger(__name__)


class CadipaCustomerPortal(CustomerPortal):

    @http.route(['/my/memberships', '/my/memberships/page/<int:page>'], 
            type='http', auth="user", website=True)
    def portal_my_memberships(self, page=1, **kw):
        """Controlador para mostrar las membresías del usuario y disponibles"""
        values = self._prepare_portal_layout_values()
        partner = request.env.user
        
        user_memberships = request.env['action.partner'].search([
            ('id', '=', partner.action_number.id)
        ])
        
        all_memberships = request.env['action.partner'].search([])
        
        membership_count = len(user_memberships)
        pager = portal_pager(
            url="/my/memberships",
            total=membership_count,
            page=page,
            step=self._items_per_page
        )
        
        values.update({
            'memberships': user_memberships,
            'available_memberships': all_memberships,
            'pager': pager,
            'default_url': '/my/memberships',
            'page_name': 'memberships',
            'has_memberships': bool(user_memberships)
        })
        
        return request.render("cadipa_appointment.portal_memberships", values)
    
    @http.route('/my/memberships/cancel/<int:membership_id>', type='http', auth="user", website=True)
    def cancel_membership_request(self, membership_id, **kw):
        """
        Controlador para solicitar cancelación de membresía
        :param membership_id: ID de la membresía a cancelar (parte de la ruta)
        :return: Redirección a la página de membresías con mensaje
        """
        membership = request.env['action.partner'].sudo().browse(membership_id)
        try:
            membership.cancel_membership()
            
            membership.message_post(
                body=f"Solicitud de cancelación enviada por {request.env.user.name}",
                subject="Solicitud de cancelación",
                message_type="comment"
            )
            
            return request.redirect('/my/memberships?success=1')
                
        except Exception as e:
            return request.redirect(f'/my/memberships?error=1&error_message={str(e)}')