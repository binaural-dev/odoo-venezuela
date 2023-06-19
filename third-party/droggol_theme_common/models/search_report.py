# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import fields, models
from odoo.http import request
from datetime import timedelta


class DrSearchReport(models.Model):
    _name = 'dr.search.report'
    _description = 'Droggol Search Report'
    _rec_name = 'search_term'

    search_term = fields.Char(readonly=True)
    search_time = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
    autocomplete_count = fields.Integer(default=0, readonly=True)
    suggestion_count = fields.Integer(default=0, readonly=True)
    category_count = fields.Integer(default=0, readonly=True)
    product_count = fields.Integer(default=0, readonly=True)
    clicked_string = fields.Char(readonly=True)
    clicked_href = fields.Char(readonly=True)
    clicked_type = fields.Selection([('product', 'Product'), ('category', 'Category'), ('autocomplete', 'Autocomplete'), ('suggestion', 'Suggestion')], readonly=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    lang_id = fields.Many2one('res.lang', string="Language", readonly=True)
    country_id = fields.Many2one('res.country', string='Country', readonly=True)
    website_id = fields.Many2one('website', string='Website', readonly=True)
    device_type = fields.Selection([('mobile', 'Mobile'), ('desktop', 'Desktop')], string='Device Type', readonly=True)

    def _add_report_entry(self, report_data):
        report_data = {k: v for k, v in report_data.items() if k in self._fields.keys()}
        report_data['lang_id'] = self.env['res.lang']._lang_get_id(self._context.get('lang'))
        if request and request.geoip:
            country_code = request.geoip.get('country_code', "")
            country = request.env['res.country'].sudo().search([('code', '=', country_code)], limit=1) if country_code else None
            if country:
                report_data['country_id'] = country.id
        report_data['website_id'] = request.website.id
        self.sudo().create(report_data)

    def _cron_auto_delete_search_report(self):
        for website in self.env['website'].search([]):
            delete_days = website._get_dr_theme_config('json_product_search').get('delete_search_report')
            if delete_days:
                last_date = fields.Datetime.now() + timedelta(days=-delete_days)
                self.search([('website_id', '=', website.id), ('search_time', '<', last_date)]).unlink()
