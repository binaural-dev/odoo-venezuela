# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import logging
import requests
from odoo import models, fields, api

logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    allow_search_fiscal_based_on_origin_warehouse = fields.Boolean("Search fiscal based on origin warehouse?",
                                                                   default=False, help="Search fiscal position based "
                                                                                       "on origin warehouse")

    def _find_partner_ept(self, vals, key_list=[], extra_domain=[]):
        """
        This function find the partner based on domain.
        This function map the keys of the key_list with the dictionary and create domain and
        if you have given the extra_domain, then it will merge with _domain (i.e _domain = _domain + extra_domain).
        @requires: vals, key_list
        @param vals: i.e {'name': 'emipro', 'street': 'address', 'street2': 'address',
        'email': 'test@test.com'...}
        @param key_list: i.e ['name', 'street', 'street2', 'email',...]
        @param extra_domain: This domain for you can pass your own custom domain.
        i.e [('name', '!=', 'test')...]
        @return: partner object or False
        """
        if key_list and vals:
            _domain = [] + extra_domain
            for key in key_list:
                if not vals.get(key):
                    continue
                if (key in vals) and isinstance(vals.get(key), str):
                    _domain.append((key, '=ilike', self._remove_special_chars(vals.get(key))))
                else:
                    _domain.append((key, '=', vals.get(key)))
            partner = self.search(_domain, limit=1) if _domain else False
            return partner
        return False

    def search_partner_by_email(self, email):
        """
        Usage : Search Partner by Email if not found then use =ilike operator for ignore case sensitive search
        and set limit 1 because it may possible to find multiple emails due to =ilike operator
        :param email: Email Id, Type: Char
        :return: res.partner()
        """
        partner = self.search([('email', '=ilike', email)], limit=1)
        return partner

    def get_country(self, country_name_or_code):
        """
            Usage : Search Country by name or code if not found then use =ilike operator for ignore case sensitive
            search and set limit 1 because it may possible to find multiple emails due to =ilike operator
            :param country_name_or_code: Country Name or Country Code, Type: Char
            :return: res.country()
        """
        country = self.env['res.country'].search(['|', ('code', '=ilike', country_name_or_code),
                                                  ('name', '=ilike', country_name_or_code)], limit=1)
        return country

    def create_or_update_state_ept(self, country_code, state_name_or_code, zip_code, country_obj=False):
        """ This method is used to search state-based country, state code or zip code.
        """
        res_country_obj = self.env['res.country.state']
        if not country_obj:
            country = self.get_country(country_code)
        else:
            country = country_obj
        state = res_country_obj.search(['|', ('name', '=ilike', state_name_or_code),
                                        ('code', '=ilike', state_name_or_code),
                                        ('country_id', '=', country.id)], limit=1)

        if not state and zip_code:
            state = self.get_state_from_api(country_code, zip_code, country)
        return state

    def get_state_from_api(self, country_code, zip_code, country):
        """
        This method tries to find state from country and zip code from zippopotam api.
        @param country_code: Code of country.
        @param zip_code: Zip code.
        @param country: Record of Country.
        @return: Record of state if found, otherwise object.
        """
        state_obj = state = self.env['res.country.state']
        country_obj = self.env['res.country']
        try:
            url = 'https://api.zippopotam.us/' + country_code + '/' + zip_code.split('-')[0]
            response = requests.get(url)
            response = ast.literal_eval(response.content.decode('utf-8'))
        except Exception as error:
            logger.info("Error when a request for state: %s", error)
            return state_obj
        if response:
            if not country:
                country = self.get_country(response.get('country abbreviation'))
            if not country:
                country = self.get_country(response.get('country'))
            if not country:
                country = country_obj.create({'name': response.get('country'),
                                              'code': response.get('country abbreviation')})
            # State search functionality is modified because using the old method there might be
            # chance to get the blank record from the database.
            state_code = response.get('places')[0].get('state abbreviation')
            state_name = response.get('places')[0].get('state', '')
            if state_code:
                state = state_obj.search([('code', '=ilike', state_code), ('country_id', '=', country.id)],
                                         limit=1)
            elif state_name:
                state = state_obj.search([('name', '=ilike', state_name), ('country_id', '=', country.id)],
                                         limit=1)
            if not state and state_code:
                state = state_obj.create({'name': state_name, 'code': state_code,
                                          'country_id': country.id})
        return state

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherited for calling onchange method.
        We got issue of not setting the gst_treatment field automatically of Indian accounting and same field is
        required and readonly in Sale order.
        """
        partner = super(ResPartner, self).create(vals_list)
        partner._onchange_country_id()
        return partner

    def remove_special_chars_from_partner_vals(self, partner_values):
        """
        Remove special Chars from end of the partner values
        :param partner_values: partner values
        :return: partner values
        """
        for key, value in partner_values.items():
            if isinstance(value, str):
                partner_values[key] = self._remove_special_chars(value)
        return partner_values

    def _remove_special_chars(self, partner_value):
        """
        Remove special chars from the end of partner value
        :param partner_value: partner value
        :return: partner value
        """
        if partner_value[-1:] == "\\":
            partner_value = partner_value[:-1]
            partner_value = self._remove_special_chars(partner_value)
        return partner_value
