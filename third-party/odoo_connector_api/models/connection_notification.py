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

import os
import logging
_logger = logging.getLogger(__name__)

import requests
from datetime import datetime

from odoo import fields, osv, models, api
from odoo.tools.translate import _
from odoo import tools

from . import versions
from .versions import *

import hashlib

class OcapiConnectionNotification(models.Model):

    _name = "ocapi.connection.notification"
    _description = "Ocapi Connection Notification"

    #Connection reference defining mkt place credentials
    connection_account = fields.Many2one( "ocapi.connection.account", string="Odoo Connector Api Connection Account" )

    notification_id = fields.Char(string='Notification Id',required=True,index=True)
    application_id = fields.Char(string='Application Id', index=True)
    user_id = fields.Char('User Id')
    topic = fields.Char('Topic', index=True)
    sent = fields.Datetime('Sent')
    received = fields.Datetime('Received', index=True)
    resource = fields.Char("Resource", index=True)
    attempts = fields.Integer('Attempts')

    state = fields.Selection([
		("RECEIVED","Notification received."),
		("PROCESSING","Processing notification."),
        ("FAILED","Notification process with errors"),
		("SUCCESS","Notification processed.")
		], string='Notification State', index=True )
    processing_started = fields.Datetime( string="Processing started" )
    processing_ended = fields.Datetime( string="Processing ended" )
    processing_errors = fields.Text( string="Processing errors log" )
    processing_logs = fields.Text( string="Processing Logs" )
    company_id = fields.Many2one("res.company",string="Company")
    seller_id = fields.Many2one("res.users",string="Seller")


    def _prepare_values(self, values):
        company = self.env.user.company_id
        seller_user_id = None
        conn_account = None
        if "connection_account" in values:
            conn_account = values["connection_account"]
            if (conn_account.configuration and conn_account.configuration.seller_user):
                seller_user_id = conn_account.configuration.seller_user.id

        vals = {
            "connection_account": (conn_account and conn_account.id) or None,
            "notification_id": values["_id"] or "missing",
            "application_id": values["application_id"],
            "user_id": values["user_id"] or "missing",
            "topic": values["topic"] or "missing",
            "resource": values["resource"] or "missing",
            "processing_started": values["processing_started"] or '',
            "received": ml_datetime(values["received"]),
            "sent": ml_datetime(values["sent"]),
            "attempts": values["attempts"] or 1,
            "state": "RECEIVED",
            'company_id': company.id,
            'seller_id': seller_user_id
        }
        return vals

    def process_notification(self):
        _logger.info("process notification")

        return False

    def start_internal_notification(self, internals):

        date_time = ml_datetime( str( datetime.now() ) )
        base_str = str(internals["application_id"]) + str(internals["user_id"]) + str(date_time)

        hash = hashlib.md5()
        hash.update( base_str.encode() )
        hexhash = str("i-")+hash.hexdigest()

        internals["processing_started"] = date_time
        internals["_id"] = hexhash
        internals["received"] = date_time
        internals["sent"] = date_time
        internals["attempts"] = 1
        internals["state"] = "RECEIVED"

        vals = self._prepare_values(values=internals)
        noti = self.create(vals)

        return  noti

    def stop_internal_notification(self, errors="", logs=""):
        self.processing_ended = ml_datetime( str( datetime.now() ) )
        self.processing_errors = str(errors)
        self.processing_logs = str(logs)
        self.state = 'SUCCESS'
