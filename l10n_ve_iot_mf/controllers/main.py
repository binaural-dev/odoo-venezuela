from odoo import http, fields, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import date_utils
from datetime import datetime
import functools
import json


class ApiIoT(http.Controller):
    @http.route(
        "/iot_fiscal/ports", type="http", auth="public", methods=["GET"], csrf=False
    )
    def getFiscalPorts(self, **kw):
        iot_ids = request.env["iot.box"].sudo().search([("has_fiscal_machine", "=", True)])
        response = {}
        for iot in iot_ids:
            response[iot.identifier] = iot.fiscal_port_ids.mapped(lambda x: x.name)
        return json.dumps(response)


    @http.route(
        "/iot_blacklist/ports", type="http", auth="public", methods=["GET"], csrf=False
    )
    def getFiscalPortsToBlock(self, **kw):
        iot_ids = request.env["iot.box"].sudo().search([("blacklist", "=", True)])
        response = {}
        for iot in iot_ids:
            response[iot.identifier] = iot.blacklist_port_ids.mapped(lambda x: x.name)
        return json.dumps(response)
