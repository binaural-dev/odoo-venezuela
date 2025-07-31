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

        values = self._prepare_portal_layout_values()
        partner = request.env.user
        
        user_memberships = request.env['action.partner'].search([
            ('id', '=', partner.action_number.id)
        ])

        user_guests = user_memberships.beneficiary_partner_ids
        
        all_memberships = request.env['membership.type.plan'].search([])
        
        membership_count = len(user_memberships)
        pager = portal_pager(
            url="/my/memberships",
            total=membership_count,
            page=page,
            step=self._items_per_page
        )
        res_partner = request.env['res.partner']

        vat_prefixes = res_partner._fields['prefix_vat'].selection
    
        values.update({
            'memberships': user_memberships,
            'guests': user_guests,
            'available_memberships': all_memberships,
            'pager': pager,
            'default_url': '/my/memberships',
            'page_name': 'memberships',
            'vat_prefixes': vat_prefixes,
            'guest_types': [(key, value) for key, value in self._get_guest_type_relation().items()],
            'type_relations': [(key, value) for key, value in self._get_type_relations_dict().items()],
            'has_memberships': bool(user_memberships)
        })
        
        return request.render("cadipa_appointment.portal_memberships", values)
    
    def _get_type_relations_dict(self):
        """
        Devuelve un diccionario para traducir los valores de selección de type_relation.
        """
        return {
            'wife': 'Esposa',
            'children': 'Hijos',
            'parents': 'Padres',
            'special_children': 'Hijos Especiales',
        }
    
    def _get_guest_type_relation(self):
        """
        Devuelve un diccionario para traducir los valores de selección de guest_type.
        """
        return {
            'family': 'Familia',
            'guest': 'Invitado',
        }

    @http.route('/my/memberships/cancel/<int:membership_id>', type='http', auth="user", website=True)
    def cancel_membership_request(self, membership_id, **kw):

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
        
    @http.route('/my/memberships/add_guest/<int:membership_id>', type='http', auth="user", website=True, methods=['POST'])
    def add_membership_guest(self, membership_id, **post):
        try:
            membership = request.env['action.partner'].browse(membership_id)
            if not membership.exists() or membership.owner_id != request.env.user.partner_id:
                return request.redirect('/my/memberships?error=no_access')
            
            guest_data = {
                'name': post.get('name'),
                'prefix_vat': post.get('vat_prefix'),
                'vat': post.get('identification'),
                'phone': post.get('phone'),
                'email': post.get('email'),
                'street': post.get('address'),
                'type_relation': post.get('type_relation') or 'n/a',
                'birthday': post.get('birthdate'),
                'parent_id': membership.owner_id.id,
                'guest_state': 'pending',
                'guest_type': post.get('guest_type'),
                'is_solvent': membership.owner_id.is_solvent,
                'start_date': membership.owner_id.start_date,
            }
            
            guest = request.env['res.partner'].sudo().with_context(website_rename_vat =True).create(guest_data)
            
            return request.redirect(f'/my/memberships?success=1&message=Invitado {guest} agregado correctamente')
            
        except Exception as e:
            return request.redirect(f'/my/memberships?error=1&error_message={str(e)}')


    @http.route('/my/memberships/delete_guest/<int:guest_id>', type='http', auth="user", website=True)
    def delete_guest(self, guest_id, **kw):
        try:
            guest = request.env['res.partner'].sudo().browse(guest_id)
            
            if guest.exists() and guest.parent_id == request.env.user.partner_id:
                guest.unlink()
                return request.redirect('/my/memberships')
            
            return request.redirect('/my/memberships?error=1&error_message=No+se+pudo+eliminar+el+invitado')
        
        except Exception as e:
            return request.redirect(f'/my/memberships?error=1&error_message={str(e)}')