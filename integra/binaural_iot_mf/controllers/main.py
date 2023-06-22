from odoo import http, fields, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import date_utils
from datetime import datetime
import functools
import json


class ApiIoT(http.Controller):
    @http.route(
        "/iot_fiscal/ports", type="http", auth="public", method=["GET"], csrf=False, website=True
    )
    def getPayments(self, **kw):
        iot_ids = request.env["iot.box"].sudo().search([("has_fiscal_machine", "=", True)])
        response = {}
        for iot in iot_ids:
            response[iot.identifier] = iot.fiscal_port_ids.mapped(lambda x: x.name)
        return json.dumps(response)
