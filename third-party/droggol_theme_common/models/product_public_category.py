# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

import re
import itertools
from odoo import fields, models, api, tools

from .search_utils import DroggolSearchTerm as DST, CategorySearchDB as CSD


class ProductPublicCategory(models.Model):
    _name = 'product.public.category'
    _inherit = ['product.public.category', 'dr.cache.mixin']
    _fields_to_watch = ['name', 'ds_synonyms_ids']

    dr_category_label_id = fields.Many2one('dr.product.public.category.label', string='Label')
    dr_category_cover_image = fields.Binary('Cover Image')
    dr_category_icon = fields.Binary('Icon Image')
    dr_category_sidebar_cover = fields.Binary('Sidebar Cover')
    dr_search_formulate = fields.Boolean('Formulated Search', help="Use to search multi level categories \
        e.g. Men Shirt (Here men and shirt are diffrent category but will be displayed as one in smart search)")
    ds_name = fields.Char('Search DS Name', compute="_compute_ds_name", search="_search_ds_name")
    ds_synonyms_ids = fields.One2many('dr.category.synonyms', 'category_id')

    def _compute_ds_name(self):
        for category in self:
            if self.env.context.get('dr_formulate'):
                category.ds_name = ' '.join([categ.name for categ in category.parents_and_self if (category.id == categ.id or categ.dr_search_formulate)])
            else:
                category.ds_name = category.name

    @api.model
    def _search_ds_name(self, operator, value):
        if not self.env.context.get('dr_formulate'):
            return [('name', operator, value)]

        # Assumes operator is 'ilike'
        domain, website_id = [('dr_search_formulate', '=', False)], self.env.context.get('website_id')
        if website_id:
            domain += self.env['website'].website_domain(website_id=website_id)
        categ_ids = [categ.id for categ in self.search(domain) if re.search(re.escape(value), categ.ds_name, re.IGNORECASE)]
        return [('id', 'in', categ_ids)]

    @api.model
    def _search_get_detail(self, website, order, options):
        "Fix the issue of Odoo's search in html fields"
        with_image = options['displayImage']
        options = options.copy()
        options['displayDescription'] = False
        result = super()._search_get_detail(website, order, options)
        if with_image:
            result['mapping']['image_url'] = {'name': 'image_url', 'type': 'html'}

        # to fix Odoo's issue Odoo catagory is not multi website compatible
        result['base_domain'] = [website.website_domain()]

        return result

    def _get_search_db(self, website):
        search_db = self._get_category_search_tuples(self._context.get('lang'), website.id)
        return CSD(search_db)

    # @api.model
    # @tools.ormcache('lang', 'website_id')
    def _get_category_search_tuples(self, lang, website_id):
        website = self.env['website'].browse(website_id)
        categories = self.search(website.website_domain())
        search_db = []

        def _add_entry(*data):
            search_db.append(DST(*data))

        for category in categories:
            parents = category.parents_and_self
            has_formulate = parents.filtered(lambda cat: cat.dr_search_formulate)

            if has_formulate:
                cartesian_list = []
                for categ in parents:
                    if category.id == categ.id or categ.dr_search_formulate:
                        cartesian_list.append([categ.name] + categ.mapped('ds_synonyms_ids.name'))
                for cp in itertools.product(*cartesian_list):
                    _add_entry(' '.join(cp), category.id, category.dr_search_formulate)
            else:
                _add_entry(category.name, category.id, category.dr_search_formulate)
                for synonym in category.ds_synonyms_ids:
                    _add_entry(synonym.name, synonym.category_id.id, category.dr_search_formulate)

        return search_db


class DrPublicCategorySynonyms(models.Model):
    _name = 'dr.category.synonyms'
    _description = 'Category Search Synonyms'

    name = fields.Char(translate=True)
    category_id = fields.Many2one('product.public.category')
    website_id = fields.Many2one('website', related="category_id.website_id", store=True)
    dr_search_formulate = fields.Boolean(related="category_id.dr_search_formulate", store=True)
    ds_name = fields.Char('Search DS Name', compute="_compute_ds_name", search="_search_ds_name")

    def _compute_ds_name(self):
        for synonym in self:
            if self.env.context.get('dr_formulate'):
                categ_formulate_names = [categ.name for categ in (synonym.category_id.parents_and_self - synonym.category_id) if (synonym.id == categ.id or categ.dr_search_formulate)]
                categ_formulate_names.append(synonym.name)
                synonym.ds_name = ' '.join(categ_formulate_names)
            else:
                synonym.ds_name = synonym.name

    @api.model
    def _search_ds_name(self, operator, value):
        if not self.env.context.get('dr_formulate'):
            return [('name', operator, value)]

        # Assumes operator is 'ilike'
        domain, website_id = [], self.env.context.get('website_id')
        if website_id:
            domain += self.env['website'].website_domain(website_id=website_id)
        categ_ids = [categ.id for categ in self.search(domain) if re.search(re.escape(value), categ.ds_name, re.IGNORECASE)]
        return [('id', 'in', categ_ids)]
