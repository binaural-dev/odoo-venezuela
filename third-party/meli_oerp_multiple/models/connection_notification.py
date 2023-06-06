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
import json
from ast import literal_eval
import random

#from .warning import warning
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
from . import versions
from .versions import *
import hashlib

class MercadoLibreConnectionNotification(models.Model):

    #_name = "mercadolibre.notification"
    #_description = "MercadoLibre Notification"
    #_inherit = "ocapi.connection.notification"
    _inherit = "mercadolibre.notification"

    #Connection reference defining mkt place credentials
    connection_account = fields.Many2one( "mercadolibre.account", string="MercadoLibre Account" )

    company = fields.Many2one("res.company",string="Noti. Company")
    user = fields.Many2one("res.users",string="User")

    limit_attempts = fields.Integer(string='Attempts limit')
    model_ids_step = fields.Integer(string='Models Step Count')
    model_ids_count = fields.Integer(string='Models Count')
    model_ids_count_processed = fields.Integer(string='Models Count Processed')
    model_ids = fields.Text(string="Models",readonly=False)
    model_ids_processed = fields.Text(string="Models Processed",readonly=False)

    def _prepare_values(self, values, company=None, account=None ):
        if not account:
            return {}
        company = (account and account.company_id) or self.env.user.company_id
        seller_id = None
        config = account.configuration
        if config.mercadolibre_seller_user:
            seller_id = config.mercadolibre_seller_user.id
        vals = {
            "connection_account": account.id,
            "notification_id": values["_id"],
            "application_id": values["application_id"],
            "user_id": values["user_id"],
            "company": ("company" in values and values["company"]) or company.id,
            "user": ("user" in values and values["user"]) or self.env.user.id,
            "topic": values["topic"],
            "resource": values["resource"],
            "received": ml_datetime(values["received"]),
            "sent": ml_datetime(values["sent"]),
            "attempts": values["attempts"],
            "state": "RECEIVED",
            'company_id': company.id,
            'seller_id': seller_id,
        }
        ("model_ids" in values) and vals.update({"model_ids": values["model_ids"] })
        ("model_ids_step" in values) and vals.update({"model_ids_step": values["model_ids_step"] })
        ("model_ids_count" in values) and vals.update({"model_ids_count": values["model_ids_count"] })
        ("model_ids_count_processed" in values) and vals.update({"model_ids_count_processed": values["model_ids_count_processed"] })
        ("processing_started" in values) and vals.update({"processing_started": values["processing_started"] })
        return vals

    def fetch_lasts( self, data=None, company=None, account=None, meli=None):

        #_logger.info("MercadoLibreConnectionNotification fetch_lasts: "+str(data)+str(company)+str(account))

        if not meli:
            meli = self.env['meli.util'].get_new_instance( account.company_id, account )

        try:
            messages = []
            if data:

                if str(meli.client_id) != str(data["application_id"]):
                    return {"error": "account.client_id and application_id does not match!", "status": "520" }

                if (not "_id" in data):
                    date_time = ml_datetime( str( datetime.now() ) )
                    base_str = str(data["application_id"]) + str(data["user_id"]) + str(date_time)
                    hash = hashlib.md5()
                    hash.update( base_str.encode() )
                    hexhash = str("n")+hash.hexdigest()
                    data["_id"] = hexhash
                messages.append(data)

            #process all notifications
            res = []
            for n in messages:
                try:
                    if ("_id" in n):
                        if (n["topic"] in ["order","created_orders","orders_v2"]):
                            nn = self.search([('notification_id','=',n["_id"])])
                            if (len(nn)==0):
                                vals = self._prepare_values(values=n, company=company, account=account)
                                if vals:
                                    #_logger.info(vals)
                                    noti = self.create(vals)
                                    _logger.info("Created new ORDER notification.")
                                    if (noti):
                                        re = noti._process_notification_order(meli=meli)
                                        if re:
                                            res.append(re)

                        if (n["topic"] in ["questions"]):
                            nn = self.search([('notification_id','=',n["_id"])])
                            if (len(nn)==0):
                                vals = self._prepare_values(values=n, company=company, account=account)
                                if vals:
                                    #_logger.info(vals)
                                    noti = self.create(vals)
                                    _logger.info("Created new QUESTION notification.")
                                    if (noti):
                                        re = noti._process_notification_question(meli=meli)
                                        if re:
                                            res.append(re)
                except Exception as e:
                    _logger.error("Error creating notification.")
                    _logger.info(e, exc_info=True)
                    return {"error": "Error creating notification.", "status": "520" }
                    pass;
            return res

            #must upgrade to /missed_feeds
            #response = meli.get("/myfeeds", {'app_id': company.mercadolibre_client_id,'offset': 1, 'limit': 10,'access_token':meli.access_token} )
            #rjson = response.json()

            #if ("messages" in rjson):
            #    for n in rjson["messages"]:
            #        messages.append(n)

        except Exception as e:
            _logger.error("Error connecting to Meli, myfeeds")
            _logger.info(e, exc_info=True)
            return {"error": "Error connecting to Meli.", "status": "520" }
            pass;

        return {"error": "Error connecting to Meli.", "status": "520" }

    def process_notification(self, context=None, meli=None):
        context = context or self.env.context
        #_logger.info("context:"+str(context))
        if context and "params" in context:
            pars = context["params"]
            if pars and ("id" in pars) and ("model" in pars) and (pars["model"] == "mercadolibre.notification"):
                self = self.browse([pars["id"]])
                #_logger.info(self)
        result = []
        for noti in self:
            #_logger.info("MercadoLibreConnectionNotification process notification")
            if noti.connection_account:
                account = noti.connection_account

                if (noti.topic in ["questions"]):
                    res = noti._process_notification_question(meli=meli)
                    if res:
                        result.append(res)

                if (noti.topic in ["order","created_orders","orders_v2"]):

                    res = noti._process_notification_order(meli=meli)
                    if res:
                        result.append(res)

                if noti.topic == "internal_job":
                    if "reprocess_force" in context and context["reprocess_force"]:
                        noti.model_ids_processed = False
                        noti.state = 'RECEIVED'
                        noti.processing_errors = ''
                        noti.processing_logs = ''
                    res = noti._process_notification_internal_job(meli=meli)
                    if res:
                        result.append(res)

                if noti.topic == "sales":
                    #sales = json.loads(noti.processing_logs)
                    sales = literal_eval(noti.processing_logs)

                    #_logger.info("Re Processing sales " + str(sales))

                    for sale in sales:
                        res = account.import_sale( sale, noti )
                        for r in res:
                            result.append(r)

                    #_logger.info("process_notification " + str(result))


        return result

    def _process_notification_order( self, meli=None):
        #_logger.info("meli_oerp_multiple >> _process_notification_order")

        account = self.connection_account
        if not account:
            return {}

        company = account.company_id or self.env.user.company_id
        config = account.configuration

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )

        for noti in self:

            noti.state = 'PROCESSING'
            #noti.attempts+= 1
            noti.processing_started = ml_datetime(str(datetime.now()))

            try:
                res = meli.get(""+str(noti.resource), {'access_token':meli.access_token} )

                ojson =  res.json()
                #_logger.info("Notification fetched: ")
                #_logger.info(ojson)

                if ('error' in ojson):
                    noti.state = 'FAILED'
                    noti.processing_errors = "Notification error:"+str(ojson)

                if ("id" in ojson):

                    morder = self.env["mercadolibre.orders"].search( [('order_id','=',ojson["id"])], limit=1 )

                    #_logger.info(str(morder))
                    pdata = { "id": False, "order_json": ojson }

                    so = None
                    if (morder and len(morder)):
                        pdata["id"] =  morder.id
                        so = morder.sale_order or None
                        #Fix auto seller team assignation, if the team company doesnt match the account company  (access issues)
                        if so:
                            so.meli_fix_team( meli=meli, config=config )



                    rsjson = morder.orders_update_order_json( data=pdata, meli=meli, config=config )
                    #_logger.info("meli_oerp_multiple >> _process_notification_order >> orders_update_order_json >> rsjson: "+str(rsjson))

                    if (rsjson and 'error' in rsjson):
                        noti.state = 'FAILED'
                        noti.processing_errors = str(rsjson['error'])
                        _logger.error("meli_oerp_multiple >> _process_notification_order >> orders_update_order_json >> rsjson error: "+noti.processing_errors)
                    else:
                        noti.state = 'SUCCESS'
                        noti.processing_errors = str(rsjson)

            except Exception as E:
                noti.state = 'FAILED'
                noti.processing_errors = str(E)
                _logger.error("meli_oerp_multiple >> _process_notification_order >> "+noti.processing_errors)
            finally:
                noti.processing_ended = ml_datetime(str(datetime.now()))

    def _process_notification_question( self, meli=None):

        #_logger.info("meli_oerp_multiple >> _process_notification_question")

        account = self.connection_account
        if not account:
            _logger.error("meli_oerp_multiple >> _process_notification_question >> Account not defined")
            return {}

        company = account.company_id or self.env.user.company_id
        config = account.configuration

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )

        for noti in self:
            noti.state = 'PROCESSING'
            #noti.attempts+= 1
            noti.processing_started = ml_datetime(str(datetime.now()))

            try:
                res = meli.get(""+str(noti.resource), {'access_token':meli.access_token} )
                ojson =  res.json()
                #_logger.info("Notification fetched: ")
                #_logger.info(ojson)

                if ('error' in ojson):
                    noti.state = 'FAILED'
                    noti.processing_errors = "Notification error:"+str(ojson)

                if ("id" in ojson):

                    #morder = self.env["mercadolibre.orders"].search( [('order_id','=',ojson["id"])], limit=1 )

                    #_logger.info(str(morder))
                    #pdata = { "id": False, "order_json": ojson }

                    #if (morder and len(morder)):
                    #    pdata["id"] =  morder.id

                    rsjson = {}
                    #question_id =
                    rsjson = self.env["mercadolibre.questions"].process_question( Question=ojson, meli=meli, config=config )
                    #rsjson = morder.orders_update_order_json( data=pdata, meli=meli, config=config )
                    #_logger.info("meli_oerp_multiple >> _process_notification_question >> rsjson: "+str(rsjson))

                    if (rsjson and 'error' in rsjson):
                        noti.state = 'FAILED'
                        noti.processing_errors = str(('message' in rsjson and rsjson['message']) or rsjson['error'])
                        _logger.error("meli_oerp_multiple >> _process_notification_question >> rsjson error: "+noti.processing_errors)
                    else:
                        noti.state = 'SUCCESS'
                        noti.processing_errors = str(rsjson)

            except Exception as E:
                noti.state = 'FAILED'
                noti.processing_errors = str(E)
                _logger.error("meli_oerp_multiple >> _process_notification_question >> "+noti.processing_errors)
            finally:
                noti.processing_ended = ml_datetime(str(datetime.now()))

    def _process_notification_internal_job( self, meli=None):
        #_logger.info("meli_oerp_multiple >> _process_notification_internal_job")

        account = self.connection_account
        if not account:
            return {}

        company = account.company_id or self.env.user.company_id
        config = account.configuration

        if not meli:
            meli = self.env['meli.util'].get_new_instance( company, account )

        for noti in self:

            noti.state = 'PROCESSING'
            noti.processing_started = ml_datetime(str(datetime.now()))
            if (config.mercadolibre_cron_post_update_stock):
                #_logger.info("config.mercadolibre_cron_post_update_stock True "+str(config.name))
                account.meli_update_remote_stock_injobs( meli=meli, notification=noti )

            if (config.mercadolibre_cron_post_update_price):
                _logger.info("config.mercadolibre_cron_post_update_price True "+str(config.name))
                #account.meli_update_remote_price_injobs( meli=meli, notification=noti )

        return {}

    def start_internal_notification(self, internals, account=None):

        noti = None
        date_time = ml_datetime( str( datetime.now() ) )
        base_str = str(internals["application_id"]) + str(internals["user_id"]) + str(date_time)

        hash = hashlib.md5()
        hash.update( base_str.encode() )
        hexhash = str("i-")+hash.hexdigest()+str("#")+str(int(random.random()*900000+100000))

        internals["processing_started"] = date_time
        internals["_id"] = hexhash
        internals["received"] = date_time
        internals["sent"] = date_time
        internals["attempts"] = 1
        internals["state"] = "RECEIVED"

        vals = self._prepare_values(values=internals, account=account)
        if vals:
            noti = self.create(vals)

        return  noti
