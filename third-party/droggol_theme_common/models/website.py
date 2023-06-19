# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.tools.translate import html_translate


class Website(models.Model):
    _inherit = 'website'

    dr_sale_special_offer = fields.Html('Sale Special Offer', sanitize_attributes=False, translate=html_translate, sanitize_form=False)

    dr_pwa_activated = fields.Boolean('PWA Activated')
    dr_pwa_name = fields.Char('PWA Name')
    dr_pwa_short_name = fields.Char('PWA Short Name')
    dr_pwa_background_color = fields.Char('PWA Background Color', default='#000000')
    dr_pwa_theme_color = fields.Char('PWA Theme Color', default='#FFFFFF')
    dr_pwa_icon_192 = fields.Binary('PWA Icon 192x192')
    dr_pwa_icon_512 = fields.Binary('PWA Icon 512x512')
    dr_pwa_start_url = fields.Char('PWA Start URL', default='/shop')
    dr_pwa_offline_page = fields.Boolean('PWA Offline Page')
    dr_pwa_version = fields.Integer('PWA Version')
    dr_pwa_shortcuts = fields.One2many('dr.pwa.shortcuts', 'website_id', string='Shortcuts')

    def _get_brands(self, domain=[], limit=None, order=None):
        brand_attributes = self._get_brand_attributes().ids
        domain = expression.AND([domain, [('attribute_id', 'in', brand_attributes)]])
        return self.env['product.attribute.value'].search(domain, limit=limit, order=order)

    def _dr_has_b2b_access(self, record=None):
        if self._get_dr_theme_config('json_b2b_shop_config')['dr_enable_b2b']:
            return not self.env.user.has_group('base.group_public')
        return True

    def _get_brand_attributes(self):
        """ This will preserver the sequence """
        current_website_products = self.env['product.template'].search(self.sale_product_domain())
        all_brand_attributes = self.env['product.template']._get_brand_attribute()
        return self.env['product.template.attribute.line'].search([('product_tmpl_id', 'in', current_website_products.ids), ('attribute_id', 'in', all_brand_attributes.ids)]).mapped('attribute_id')

    def get_dr_theme_config(self):
        return self._get_dr_theme_config()

    def _get_dr_theme_config(self, key=False):
        """ See dr.theme.config for more info"""
        self.ensure_one()
        website_config = self.env['dr.theme.config']._get_all_config(self.id)
        website_config['is_public_user'] = not self.env.user.has_group('website.group_website_restricted_editor')
        website_config['has_sign_up'] = False
        if website_config.get('json_b2b_shop_config')['dr_enable_b2b']:
            website_config['has_sign_up'] = self.env['res.users']._get_signup_invitation_scope() == 'b2c'
        if key:
            return website_config.get(key)
        return website_config

    def get_current_pricelist(self):
        if self._get_dr_theme_config('json_b2b_shop_config')['dr_only_assigned_pricelist'] and not self.env.user.has_group('base.group_website_designer'):
            return self.env.user.partner_id.property_product_pricelist
        return super().get_current_pricelist()

    def _dr_website_has_theme_prime(self):
        return self._get_dr_theme_config('theme_installed')

    def get_pricelist_available(self, show_visible=False):
        if self._get_dr_theme_config('json_b2b_shop_config')['dr_only_assigned_pricelist'] and not self.env.user.has_group('base.group_website_designer'):
            return self.env.user.partner_id.property_product_pricelist
        return super().get_pricelist_available(show_visible=show_visible)

    @api.model
    def get_theme_prime_shop_config(self):
        Website = self.get_current_website()
        return {
        'is_rating_active': Website.sudo().viewref('website_sale.product_comment').active, 
        'is_buy_now_active': Website.sudo().viewref('website_sale.product_buy_now').active, 
        'is_multiplier_active': Website.sudo().viewref('website_sale.product_quantity').active, 
        'is_wishlist_active': Website.sudo().viewref('website_sale_wishlist.product_add_to_wishlist').active, 
        'is_comparison_active': Website.sudo().viewref('website_sale_comparison.add_to_compare').active}

    def _get_website_category(self):
        return self.env['product.public.category'].search([('website_id', 'in', [False, self.id]), ('parent_id', '=', False)])

    def _get_theme_prime_rating_template(self, rating_avg, rating_count=False):
        return self.env['ir.ui.view']._render_template('theme_prime.d_rating_widget_stars_static', values={
            'rating_avg': rating_avg,
            'rating_count': rating_count,
        })

    @api.model
    def get_theme_prime_bottom_bar_action_buttons(self):
        # Add to cart, blog, checkout, pricelist, language,
        return {'tp_home': {'name': _("Home"), 'url': '/', 'icon': 'fa fa-home'}, 'tp_search': {'name': _("Search"), 'icon': 'dri dri-search', 'action_class': 'tp-search-sidebar-action'}, 'tp_wishlist': {'name': _("Wishlist"), 'icon': 'dri dri-wishlist', 'url': '/shop/wishlist'}, 'tp_offer': {'name': _("Offers"), 'url': '/offers', 'icon': 'dri dri-bolt'}, 'tp_brands': {'name': _("Brands"), 'icon': 'dri dri-tag-l ', 'url': '/shop/all-brands'}, 'tp_category': {'name': _("Category"), 'icon': 'dri dri-category', 'action_class': 'tp-category-action'}, 'tp_orders': {'name': _("Orders"), 'icon': 'fa fa-file-text-o', 'url': '/my/orders'}, 'tp_cart': {'name': _("Cart"), 'icon': 'dri dri-cart', 'url': '/shop/cart'}, 'tp_lang_selector': {'name': _("Language and Pricelist selector")}}

    def _is_snippet_used(self, snippet_module, snippet_id, asset_version, asset_type, html_fields):
        """ There is no versioning for all theme snippets (for the test case)"""
        if snippet_module and snippet_module.startswith('theme_prime'):
            return True
        return super()._is_snippet_used(snippet_module, snippet_id, asset_version, asset_type, html_fields)


class WebsiteSaleExtraField(models.Model):
    _inherit = 'website.sale.extra.field'

    dr_label = fields.Char('Display Label', translate=True)
    field_id = fields.Many2one('ir.model.fields', domain=[('model_id.model', '=', 'product.template'), '|', ('ttype', 'in', ['char', 'binary']), ('name', 'in', ['public_categ_ids'])])
