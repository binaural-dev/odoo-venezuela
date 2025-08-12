import logging
from odoo import http
from odoo.http import request, Response
from odoo.addons.sale.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

class CadipaSubscriptionPortal(CustomerPortal):
    
    @http.route(['/memberships/payment/preview/<int:plan_id>'], 
            type='http', auth="user", website=True)
    def subscription_payment_preview(self, plan_id, **kw):
        """
        Muestra la vista previa del pago para una suscripción
        :param plan_id: ID del plan de suscripción (sale.subscription.plan)
        """
        _logger.info('entraaaaa')
        if request.env.user._is_public():
            return request.redirect("/web/signup")
        
        subscription_plan = request.env['sale.subscription.plan'].sudo().search([])
        if not subscription_plan:
            return request.redirect('/my/memberships?error=plan_not_found')
        
        partner = request.env.user.partner_id
        
        # Obtener beneficios del plan si existen
        benefits = subscription_plan.benefit_ids if hasattr(subscription_plan, 'benefit_ids') else False
        
        values = {
            'plan': subscription_plan,
            'partner': partner,
            'page_name': 'subscription_payment_preview',
            'benefits': benefits,
            'has_benefits': bool(benefits),
        }
        
        return request.render("cadipa_subscription.subscription_payment_preview", values)
    
    @http.route(['/memberships/payment/process'], 
                type='http', auth="user", website=True, methods=['POST'])
    def process_subscription_payment(self, **post):
        """
        Procesa el pago de la suscripción
        """
        try:
            plan_id = int(post.get('plan_id'))
            subscription_plan = request.env['sale.subscription.plan'].sudo().browse(plan_id)
            
            if not subscription_plan.exists():
                return request.redirect('/my/memberships?error=plan_not_found')
            
            # Aquí iría la lógica para crear la suscripción y procesar el pago
            # Por ahora solo redireccionamos a la página de membresías con mensaje de éxito
            return request.redirect('/my/memberships?success=1&message=Payment+processed+successfully')
            
        except Exception as e:
            _logger.error("Error processing subscription payment: %s", str(e))
            return request.redirect(f'/my/memberships?error=1&error_message={str(e)}')