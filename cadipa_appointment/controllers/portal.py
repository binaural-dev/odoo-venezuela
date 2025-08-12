import logging
import json
from odoo import _, http, fields
from odoo.http import request, route,Response
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
            type='http', auth="public", website=True)
    def portal_my_memberships(self, page=1, **kw):
        # if request.env.user._is_public():
        #     return request.redirect("/web/signup")

        values = self._prepare_portal_layout_values()
        partner = request.env.user
        
        user_memberships = request.env['action.partner'].search([
            ('id', '=', partner.action_number.id),
        ])

        user_guests = user_memberships.beneficiary_partner_ids
        
        all_memberships = request.env['membership.type.plan'].sudo().search([('published', '=', True)])
        
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
        

    @http.route(['/my/memberships/select/<int:membership_plan_id>'], type='http', auth="public", website=True)
    def select_membership_plan(self, membership_plan_id, **kw):
        # Verificar si el usuario está autenticado
        if request.env.user._is_public():
            return request.redirect("/web/signup")
        
        membership_plan = request.env['membership.type.plan'].sudo().browse(membership_plan_id)
        if not membership_plan.exists():
            return request.redirect('/my/memberships?error=plan_not_found')
        
        user = request.env.user
        contact = user.partner_id
        
        required_fields = {
            'vat': "Identificación",
            'street': "Dirección",
            'municipality': "Municipio",
            'parish_id': "Parroquia",
            'prefix_vat': "Prefijo",
            'country_id': "Pais",
            'city_id': "Ciudad",

        }
        
        missing_fields = [name for field, name in required_fields.items() if not getattr(contact, field)]
        
        if missing_fields:
            return request.redirect(f'/my/memberships/additional_info/{membership_plan_id}?missing_fields={",".join(missing_fields)}')
        
        return request.redirect(f'/memberships/payment/preview/{membership_plan.product_id.id}')

    @http.route(['/my/memberships/additional_info/<int:membership_plan_id>'], 
                type='http', auth="user", website=True)
    def additional_info_form(self, membership_plan_id, **kw):
        missing_fields = kw.get('missing_fields', '').split(',')
        membership_plan = request.env['membership.type.plan'].sudo().browse(membership_plan_id)
        
        values = {
            'membership_plan': membership_plan,
            'missing_fields': missing_fields,
            'page_name': 'additional_info',
            'partner': request.env.user.partner_id,
            'municipalities': request.env['res.country.state'].search([]),
            'countries': request.env['res.country'].search([]),
            'cities': request.env['res.country.city'].sudo().search([]),


        }
        
        return request.render("cadipa_appointment.additional_info_form_view", values)
    
    @http.route('/my/memberships/save_additional_info', type='http', auth="user", website=True, methods=['POST'])
    def save_additional_info(self, **post):
        partner = request.env.user.partner_id

        def _to_int(val):
            try:
                return int(val) if val not in (None, '', False) else None
            except Exception:
                return None

        def _clean_id(model_name, raw_id):
            rec_id = _to_int(raw_id)
            if not rec_id:
                return None
            rec = request.env[model_name].sudo().browse(rec_id)
            return rec.id if rec.exists() else None

        try:
            update_vals = {}

            # Campos libres
            vat = (post.get('vat') or '').strip()
            street = (post.get('street') or '').strip()
            if vat:
                update_vals['vat'] = vat
            if street:
                update_vals['street'] = street

            country_id = _clean_id('res.country', post.get('country_id'))
            state_id = _clean_id('res.country.state', post.get('state_id'))
            city_id = _clean_id('res.country.city', post.get('city_id'))                        # tu modelo de ciudades
            municipality_id = _clean_id('res.country.municipality', post.get('municipality_id'))# ajusta si tu modelo se llama distinto
            parish_id = _clean_id('res.country.parish', post.get('parish_id'))  
            zip_int = _to_int((post.get('zip') or '').strip())

            if country_id:
                update_vals['country_id'] = country_id
            if state_id:
                update_vals['state_id'] = state_id
            if city_id:
                update_vals['city_id'] = city_id
            if municipality_id:
                update_vals['municipality'] = municipality_id  # <-- corregido el nombre del campo
            if parish_id:
                update_vals['parish_id'] = parish_id
            if zip_int:
                update_vals['zip'] = zip_int

            # Escribe solo si hay algo que guardar
            if update_vals:
                partner.sudo().write(update_vals)

            return request.redirect("/my/memberships")

        except Exception as e:
            _logger.exception("Error saving additional info: %s", e)
            membership_plan_id = post.get('membership_plan_id') or ''
            suffix = f'/{membership_plan_id}' if membership_plan_id else ''
            return request.redirect(f'/my/memberships/additional_info{suffix}?error=1')


        

    @http.route('/cadipa/location/municipalities', type='http', auth='public', website=True, methods=['GET'])
    def cadipa_get_municipalities(self, **kw):
        # 🔽 ahora por state_id
        state_id = kw.get('state_id') or request.params.get('state_id')
        state = request.env['res.country.state'].sudo().search([('id','=',state_id)])

        Municipality = request.env['res.country.municipality'].sudo()   # <-- ajusta al modelo real
        recs = Municipality.search([('state_id', '=', state.id)], order='name')
        _logger.info(f'akkskakakak === {recs}')
        return Response(json.dumps([{'id': r.id, 'name': r.name} for r in recs]), content_type='application/json')


    @http.route('/cadipa/location/parishes', type='http', auth='public', website=True, methods=['GET'])
    def cadipa_get_parishes(self, **kw):
        municipality_id =int( kw.get('municipality_id') or request.params.get('municipality_id'))
        Parish = request.env['res.country.parish'].sudo()               # <-- ajusta al modelo real
        recs = Parish.search([('municipality_id', '=', municipality_id)], order='name')
        _logger.info(f'parishhh === {recs}')
        return Response(json.dumps([{'id': r.id, 'name': r.name} for r in recs]), content_type='application/json')
    
    @http.route([
    '/cadipa/location/cities',
    '/cadipa/location/cities/<int:country_id>',
    ], type='http', auth='public', website=True, methods=['GET'])
    def cadipa_get_cities(self, country_id=None, **kw):
        state_id = kw.get('state_id') or request.params.get('state_id')
        # try:
        #     cid = int(cid)
        # except Exception:
        #     return Response(json.dumps([]), content_type='application/json')
        state = request.env['res.country.state'].sudo().search([('id','=',state_id)])

        City = request.env['res.country.city'].sudo()
        recs = City.search([('state_id', '=', state.id)], order='name')
        data = [{'id': r.id, 'name': r.name} for r in recs]
        return Response(json.dumps(data), content_type='application/json')

    @http.route(['/cadipa/location/states'], type='http', auth='public', website=True, methods=['GET'])
    def cadipa_get_states(self, **kw):
        country_id = kw.get('country_id') or request.params.get('country_id')
        try:
            country_id = int(country_id)
        except Exception:
            return Response(json.dumps([]), content_type='application/json')

        State = request.env['res.country.state'].sudo()
        recs = State.search([('country_id', '=', country_id)], order='name')
        data = [{'id': r.id, 'name': r.name} for r in recs]
        return Response(json.dumps(data), content_type='application/json')