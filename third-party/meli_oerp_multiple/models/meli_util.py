# -*- coding: utf-8 -*-

import pytz

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _

import requests
import json
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
import logging
_logger = logging.getLogger(__name__)

#from ..melisdk.sdk3 import meli
import meli
from meli.rest import ApiException
from meli.api_client import ApiClient
from odoo.addons.meli_oerp.models.meli_util import MeliApi
from odoo.addons.meli_oerp.models.meli_util import configuration

from datetime import datetime

class MeliApi( MeliApi ):

    meli_login_id = None

    def auth_url(self, redirect_URI=None):

        now = datetime.now()
        url = ""

        if redirect_URI:
            self.redirect_uri = redirect_URI

        random_id = str(now)
        params = { 'client_id': self.client_id, 'response_type':'code', 'redirect_uri': self.redirect_uri, 'state': random_id}

        #if self.meli_login_id:
        #    url_login_meli = url_login_meli + str("/") + str(self.meli_login_id)

        #url = self.AUTH_URL + str("/") + str(self.meli_login_id)
        url = self.AUTH_URL + '?' + urlencode(params)

        #_logger.info("Authorize Login here: "+str(url))
        return url

    def redirect_login(self):

        url_login_meli = str(self.auth_url())

        if self.meli_login_id:
            url_login_meli = url_login_meli + str("/") + str(self.meli_login_id)

        return {
            "type": "ir.actions.act_url",
            "url": url_login_meli,
            "target": "self",
        }

class MeliUtilMultiple(models.AbstractModel):

    _inherit = 'meli.util'

    def get_meli_state( self ):
        return self.get_new_instance()

    @api.model
    def get_new_instance(self, company=None, account=None):

        #_logger.info("MeliUtilMultiple.get_new_instance: " + str(account) )

        if not account:
            _logger.info("no account: " + str(account) )
        else:
            company = account.company_id

        if not company:
            company = self.env.user.company_id

        api_client = ApiClient()
        api_rest_client = MeliApi(api_client)
        api_rest_client.meli_login_id = (account and account.meli_login_id)
        api_rest_client.client_id = (account and account.client_id) or ''
        api_rest_client.client_secret = (account and account.secret_key) or ''
        api_rest_client.access_token = (account and account.access_token)  or ''
        api_rest_client.refresh_token = (account and account.refresh_token) or ''
        api_rest_client.redirect_uri = (account and account.redirect_uri) or ''
        api_rest_client.seller_id = (account and account.seller_id) or ''
        api_rest_client.AUTH_URL = company.get_ML_AUTH_URL(meli=api_rest_client)
        api_auth_client = meli.OAuth20Api(api_client)
        grant_type = 'authorization_code' # or 'refresh_token' if you need get one new token
        last_token = api_rest_client.access_token

        #api_response = api_instance.get_token(grant_type=grant_type, client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, code=CODE, refresh_token=REFRESH_TOKEN)
        #taken from res.company get_meli_state()
        api_rest_client.needlogin_state = False
        message = "Login to ML needed in Odoo."

        if not account:
            return api_rest_client

        #pdb.set_trace()
        try:
            if not (account.seller_id==False) and api_rest_client.access_token!='':
                response = api_rest_client.get("/users/"+str(account.seller_id), {'access_token':api_rest_client.access_token} )

                #_logger.info("get_new_instance connection response:"+str(response))
                rjson = response.json()

                status = "status" in rjson and rjson["status"]
                cause = "cause" in rjson and rjson["cause"]

                if status==500 and cause=="Internal Server Error":
                   return api_rest_client


                #_logger.info(rjson)
                if "error" in rjson:

                    if account.cron_refresh:
                        internals = {
                            "application_id": account.client_id,
                            "user_id": account.seller_id,
                            "topic": "internal",
                            "resource": "get_new_instance #"+str(account.name),
                            "state": "PROCESSING"
                        }
                        noti = self.env["mercadolibre.notification"].start_internal_notification( internals, account=account )

                        errors = str(rjson)+"\n"
                        logs = str(rjson)+"\n"

                        api_rest_client.needlogin_state = True

                        _logger.error(rjson)

                        if rjson["error"]=="not_found":
                            api_rest_client.needlogin_state = True
                            logs+= "NOT FOUND"+"\n"

                        if "message" in rjson:
                            message = rjson["message"]
                            if "message" in message:
                                #message is e.body, fix thiss
                                try:
                                    mesjson = json.loads(message)
                                    message = mesjson["message"]
                                except:
                                    message = "invalid_token"
                                    pass;
                            logs+= str(message)+"\n"
                            _logger.info("message: " +str(message))
                            if (message=="expired_token" or message=="invalid_token" or message=="internal_server_error"):
                                api_rest_client.needlogin_state = True
                                try:
                                    #refresh = meli.get_refresh_token()
                                    refresh = api_rest_client.get_refresh_token()
                                    _logger.info("Refresh result: "+str(refresh))
                                    if (refresh):
                                        #refjson = refresh.json()
                                        refjson = refresh
                                        logs+= str(refjson)+"\n"
                                        if "access_token" in refjson:
                                            api_rest_client.access_token = refjson["access_token"]
                                            api_rest_client.refresh_token = refjson["refresh_token"]
                                            api_rest_client.code = ''
                                            account.write({ 'access_token': api_rest_client.access_token,
                                                            'refresh_token': api_rest_client.refresh_token,
                                                            'code': '' } )
                                            api_rest_client.needlogin_state = False
                                except Exception as e:
                                    errors += str(e)
                                    logs += str(e)
                                    _logger.error(e)
                                    pass;
                                except:
                                    pass;

                        noti.stop_internal_notification( errors=errors , logs=logs )

                else:
                    #saving user info, brand, official store ids, etc...
                    #if "phone" in rjson:
                    #    _logger.info("phone:")
                    response.user = rjson


            else:
                api_rest_client.needlogin_state = True

            #        except requests.exceptions.HTTPError as e:
            #            _logger.info( "And you get an HTTPError:", e.message )

        except requests.exceptions.ConnectionError as e:
            #raise osv.except_osv( _('MELI WARNING'), _('NO INTERNET CONNECTION TO API.MERCADOLIBRE.COM: complete the Cliend Id, and Secret Key and try again'))
            api_rest_client.needlogin_state = True
            error_msg = 'MELI WARNING: NO INTERNET CONNECTION TO API.MERCADOLIBRE.COM: complete the Cliend Id, and Secret Key and try again '
            _logger.error(error_msg)

        if api_rest_client.access_token=='' or api_rest_client.access_token==False:
            api_rest_client.needlogin_state = True

        try:
            if api_rest_client.needlogin_state:
                _logger.warning( "Need login for " + str(account.name) )

                if ( account.cron_refresh and company.mercadolibre_cron_refresh and company.mercadolibre_cron_mail):
                    company.write({'mercadolibre_access_token': '', 'mercadolibre_refresh_token': '', 'mercadolibre_code': '', 'mercadolibre_cron_refresh': False } )
                    account.write({'access_token': '', 'refresh_token': '', 'code': '', 'cron_refresh': False } )

                    # we put the job_exception in context to be able to print it inside
                    # the email template
                    context = {
                        'job_exception': message,
                        'dbname': self._cr.dbname,
                    }

                    _logger.info(
                        "Sending scheduler error email with context=%s", context)
                    _logger.info("Sending to company:" + str(company.name)+ " mail:" + str(company.email)  )
                    rese = self.env['mail.template'].browse(
                                company.mercadolibre_cron_mail.id
                            ).with_context(context).sudo().send_mail( (company.id), force_send=True)
                    _logger.info("Result sending:" + str(rese) )
                company.write({'mercadolibre_access_token': '', 'mercadolibre_refresh_token': '', 'mercadolibre_code': '', 'mercadolibre_cron_refresh': False } )
                account.write({'access_token': '', 'refresh_token': '', 'code': '', 'cron_refresh': False } )

        except Exception as e:
            _logger.error(e)

        #if api_rest_client.needlogin_state:
        #    account.status = "disconnected"
        #else:
        #    account.status = "connected"

        for acc in account:
            if (last_token!=acc.access_token):#comp.mercadolibre_state!=api_rest_client.needlogin_state:
                _logger.info("meli_oerp_multiple account.state : "+str(api_rest_client.needlogin_state))
                astate = api_rest_client.needlogin_state
                if astate:
                    acc.status = "disconnected"
                else:
                    acc.status = "connected"
            #else:
            #    _logger.info("mercadolibre_state already set: "+str(api_rest_client.needlogin_state))

        return api_rest_client

    @api.model
    def get_url_meli_login(self, app_instance):
        if not company:
            company = self.env.user.company_id
        REDIRECT_URI = company.mercadolibre_redirect_uri
        url_login_meli = app_instance.auth_url(redirect_URI=REDIRECT_URI)
        return {
            "type": "ir.actions.act_url",
            "url": url_login_meli,
            "target": "self",
        }
