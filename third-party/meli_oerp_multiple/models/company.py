# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
#from .warning import warning
import requests

class ResCompany(models.Model):
    #_name = "res.company"
    _inherit = "res.company"

    mercadolibre_connections = fields.Many2many( "mercadolibre.account", string="MercadoLibre Connection Accounts", help="MercadoLibre Connection Accounts" )

    def get_meli_state( self ):
        # recoger el estado y devolver True o False (meli)
        #False if logged ok
        #True if need login
        _logger.info('meli_oerp_multiple company get_meli_state() ')
        company = self or self.env.user.company_id
        for comp in company:
            #company = self or self.env.user.company_id
            #_logger.info( 'meli_oerp_multiple company get_meli_state() ' + comp.name )
            #meli = self.env['meli.util'].get_new_instance(company)
            #if meli:
            comp.mercadolibre_state = True

            for account in comp.mercadolibre_connections:
                _logger.info('get_connector_state for: ' +str(comp.name) + str(" >> ") + str(account.name))
                account.get_connector_state()

    def cron_meli_orders( self ):
        _logger.info("company cron_meli_orders need to check all accounts now")
        company = self or self.env.user.company_id
        for comp in company:

            for account in comp.mercadolibre_connections:

                _logger.info('conr_meli_process for: ' +str(comp.name) + str(" >> ") + str(account.name))
                account.cron_meli_orders()

    def meli_query_orders(self):
        _logger.info("meli_oerp_multiple >> meli_query_orders")
        company = self or self.env.user.company_id
        result = []
        for comp in company:
            res = {}
            for account in comp.mercadolibre_connections:

                _logger.info('meli_query_orders for: ' +str(comp.name) + str(" >> ") + str(account.name))
                res = account.meli_query_orders()
                if (res):
                    result.append(res)

        return result

    def cron_meli_questions( self ):
        _logger.info("meli_oerp_multiple >> cron_meli_questions")
        company = self or self.env.user.company_ids or self.env.user.company_id
        _logger.info("meli_oerp_multiple >> cron_meli_questions >> company:"+str(company))
        result = []
        for comp in company:
            res = {}
            for account in comp.mercadolibre_connections:

                _logger.info('calling meli_query_get_questions for: ' +str(comp.name) + str(" >> ") + str(account.name))
                config = account and account.configuration

                if config and config.mercadolibre_cron_get_questions:
                    res = account.meli_query_get_questions()
                    if (res):
                        result.append(res)

        return result

    def cron_meli_process( self ):
        _logger.info("company cron_meli_process need to check all accounts now")
        company = self or self.env.user.company_id
        for comp in company:

            for account in comp.mercadolibre_connections:

                _logger.info('conr_meli_process for: ' +str(comp.name) + str(" >> ") + str(account.name))
                account.cron_meli_process()

    def meli_query_products(self):
        _logger.info("meli_oerp_multiple >> meli_query_products")
        company = self or self.env.user.company_id
        for comp in company:

            for account in comp.mercadolibre_connections:

                _logger.info('meli_query_products for: ' +str(comp.name) + str(" >> ") + str(account.name))
                account.meli_query_products()

        return result

    def cron_meli_process_internal_jobs(self):
        _logger.info("company cron_meli_process_internal_jobs")
        company = self or self.env.user.company_id
        for comp in company:

            for account in comp.mercadolibre_connections:

                _logger.info('cron_meli_process_internal_jobs for: ' +str(comp.name) + str(" >> ") + str(account.name))
                account.cron_meli_process_internal_jobs()


    def cron_meli_process_post_stock( self, meli=None ):

        company = self or self.env.user.company_id

        for comp in company:

            for account in comp.mercadolibre_connections:
                config = account.configuration
                if (config.mercadolibre_cron_post_update_stock):
                    _logger.info("config.mercadolibre_cron_post_update_stock")
                    account.meli_update_remote_stock(meli=meli)

    def cron_meli_process_post_price( self, meli=None ):

        company = self or self.env.user.company_id

        for comp in company:

            for account in comp.mercadolibre_connections:
                config = account.configuration
                if (config.mercadolibre_cron_post_update_price):
                    _logger.info("config.mercadolibre_cron_post_update_price")
                    account.meli_update_remote_price(meli=meli)



    def cron_meli_process_post_products( self, meli=None ):

        company = self or self.env.user.company_id

        for comp in company:

            for account in comp.mercadolibre_connections:
                config = account.configuration
                if (config.mercadolibre_cron_post_update_products or config.mercadolibre_cron_post_new_products):
                    _logger.info("config.mercadolibre_cron_post_update_products or config.mercadolibre_cron_post_new_products")
                    account.meli_update_remote_products(post_new=config.mercadolibre_cron_post_new_products)

    def cron_meli_process_get_products( self, meli=None ):

        company = self or self.env.user.company_id

        for comp in company:

            for account in comp.mercadolibre_connections:
                config = account.configuration
                if (config.mercadolibre_cron_get_update_products):
                    _logger.info("config.mercadolibre_cron_get_update_products")
                    account.meli_update_local_products()

                if (config.mercadolibre_cron_get_new_products):
                    _logger.info("config.mercadolibre_cron_get_new_products")
                    account.product_meli_get_products()
