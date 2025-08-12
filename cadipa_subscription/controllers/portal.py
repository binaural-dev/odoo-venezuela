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
        _logger.error('Plan no encontrado: %s', plan_id)

        if request.env.user._is_public():
            return request.redirect("/web/signup")
        
        subscription_plan = request.env['sale.subscription.plan'].sudo().search([],limit=1)
        if not subscription_plan:
            return request.redirect('/my/memberships?error=plan_not_found')
        
        pricing_ids = subscription_plan.product_subscription_pricing_ids
        partner = request.env.user.partner_id
        fee_product = subscription_plan.initial_fee_product

        membership_fee = False
        fee_price = False
        tax_amount = False
        membership_product = False

        for line in pricing_ids:
            for membership in line.product_template_id:
                for product in membership.product_variant_id:
                    if product.id == plan_id:
                        membership_fee = line.price
                        tax_amount = product.taxes_id.amount
                        membership_product = membership
                        membership_price = line.price

                    if subscription_plan.activation_initial_percentage>0:
                        fee_price = membership_fee*(subscription_plan.activation_initial_percentage/100)
                        fee_product.write({'list_price':fee_price})
                    else:
                        fee_price = fee_product.price
            
        benefits = subscription_plan.benefit_ids if hasattr(subscription_plan, 'benefit_ids') else False
        
        fee_price_tax = fee_price * (tax_amount/100)
        total_price = fee_price + fee_price_tax
        
        values = {
            'plan': subscription_plan,
            'fee_price': fee_price,
            'fee_price_tax':fee_price_tax,
            'membership': membership_product,
            'membership_price': membership_price,
            'total_price':total_price,
            'partner': partner,
            'page_name': 'subscription_payment_preview',
            'benefits': benefits,
            'has_benefits': bool(benefits),
        }
        
        return request.render("cadipa_subscription.subscription_payment_preview", values)
    
    @http.route(['/memberships/payment/process/<int:plan_id>'], 
            type='http', auth="user", website=True, methods=['POST'])
    def process_subscription_payment(self, plan_id, **post):
        """
        Procesa el pago de la suscripción y crea:
        1. Orden de venta
        2. Suscripción (membership)
        3. Redirección al pago
        """
        _logger.info('Iniciando proceso de pago para plan ID: %s', plan_id)
        
        try:
            # Obtener el plan de membresía
            plan = request.env['membership.type.plan'].browse(plan_id)
            if not plan:
                raise ValueError("Plan de membresía no encontrado")
            pricing_ids = subscription_plan.product_subscription_pricing_ids
            for line in pricing_ids:
                for membership in line.product_template_id:
                    for product in membership.product_variant_id:
                        if product.id == plan_id:
                            membership_fee = line.price
                            tax_amount = product.taxes_id.amount
                            membership_product = membership
                            membership_price = line.price
            
            # Obtener el usuario actual
            partner = request.env.user.partner_id
            _logger.info('Cliente: %s', partner.name)
            
        #     # Crear la orden de venta
            sale_order = request.env['sale.order'].create({
                'partner_id': partner.id,
                'order_line': [(0, 0, {
                    'product_id': plan.initial_fee_product.id,
                    'product_uom_qty': 1,
                    'price_unit': plan.initial_fee_product.list_price,
                })]
            })
            _logger.info('Orden de venta creada: %s', sale_order.name)
            
            # Confirmar la orden de venta
            sale_order.action_confirm()
            _logger.info('Orden de venta confirmada')
            membership_type = request.env['membership.type.plan'].sudo().search([("product_id","=",)])
            # Crear la membresía/suscripción
            membership = request.env['action.partner'].create({
                'owner_id': partner.id,
                'membership_plan_id': plan.id,
                'sale_order_id': sale_order.id,
                'start_date': fields.Date.today(),
                'state': 'pending',
            })
            _logger.info('Membresía creada: %s', membership.id)
            
        #     # Redireccionar al pago
        #     payment_acquirer = request.env['payment.acquirer'].search([
        #         ('state', '=', 'enabled'),
        #         ('company_id', '=', request.env.company.id)
        #     ], limit=1)
            
        #     if not payment_acquirer:
        #         raise ValueError("No hay métodos de pago configurados")
            
        #     payment_link = sale_order._get_payment_url()
        #     _logger.info('Redireccionando a: %s', payment_link)
            
        #     return request.redirect(payment_link)
        
        # except Exception as e:
        #     _logger.error('Error en process_subscription_payment: %s', str(e))
        #     return request.redirect('/web#error=' + str(e))

