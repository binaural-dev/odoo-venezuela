import logging
from odoo import http
from odoo import fields
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
        membership_price = 0.00

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
                        fee_price = fee_product.list_price
            
        benefits = subscription_plan.benefit_ids if hasattr(subscription_plan, 'benefit_ids') else False
        
        fee_price_tax = fee_price * (tax_amount/100)
        total_price = fee_price + fee_price_tax
        values = {
            'plan': subscription_plan,
            'fee_price': fee_price,
            'fee_price_tax':fee_price_tax,
            'membership': membership_product,
            'membership_id': plan_id,
            'membership_price': membership_price ,
            'total_price':total_price,
            'partner': partner,
            'page_name': 'subscription_payment_preview',
            'benefits': benefits,
            'has_benefits': bool(benefits),
        }
        
        return request.render("cadipa_subscription.subscription_payment_preview", values)
    
    @http.route(['/memberships/payment/process/<int:plan_id>/<int:membership_id>'], 
            type='http', auth="user", website=True, methods=['POST'])
    def process_subscription_payment(self, plan_id,membership_id, **post):
        """
        Procesa el pago de la suscripción y crea:
        1. Orden de venta
        2. Suscripción (membership)
        3. Redirección al pago
        """
        today = fields.Date.today()
        membership_type = request.env['membership.type.plan'].sudo().search([("product_id","=",membership_id),("published","=",True)],limit=1)
        plan = request.env['sale.subscription.plan'].sudo().browse(plan_id)



        if not plan:
            raise ValueError("Plan de membresía no encontrado")
        pricing_ids = plan.product_subscription_pricing_ids
        for line in pricing_ids:
            for membership in line.product_template_id:
                for product in membership.product_variant_id:
                    if product.id == membership_type.product_id.id:
                        membership_fee = line.price
                        tax_amount = product.taxes_id.amount
                        membership_product = membership
                        membership_price = line.price
        

        partner = request.env.user.partner_id
        
        sale_order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': membership_type.product_id.id,
                'product_uom_qty': 1,
                'price_unit': plan.initial_fee_product.list_price,
            })]
        })
        
        created_membership = request.env['action.partner'].sudo().create({
            'owner_id': partner.id,
            'membership_type_plan': membership_type.id,
            'state': 'draft',
        })
        created_membership.action_confirm()
        
        partner.write({'action_number':created_membership.id})

        return request.redirect('/my/memberships')