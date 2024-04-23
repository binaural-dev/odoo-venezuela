from odoo import models, _


class ShopifyOnboardingConfirmationEpt(models.TransientModel):
    _name = 'shopify.onboarding.confirmation.ept'
    _description = 'Shopify Onboarding Confirmation'

    def yes(self):
        """
           Usage: Save the Cron Changes by Instance Wise
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        instance_id = self._context.get('shopify_instance_id', False)
        if instance_id:
            instance = self.env['shopify.instance.ept'].browse(instance_id)
            company = instance.shopify_company_id
            company.write({
                'shopify_instance_onboarding_state': 'not_done',
                'shopify_basic_configuration_onboarding_state': 'not_done',
                'shopify_financial_status_onboarding_state': 'not_done',
                'shopify_cron_configuration_onboarding_state': 'not_done',
                'is_create_shopify_more_instance': False
            })
            instance.write({'is_onboarding_configurations_done': True})
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': _(
                        "Congratulations, You have done All Configurations of the instance: %s", str(instance.name)),
                    'img_url': '/web/static/src/img/smile.svg',
                    'type': 'rainbow_man',
                }
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def no(self):
        """
           Usage: Unsave the changes and reload the page.
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: action of reload the page
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
