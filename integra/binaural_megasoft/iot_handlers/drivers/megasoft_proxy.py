from odoo import http
import requests
import json


class MegasoftController(http.Controller):
    @http.route(["/megasoft/cambio/"], type="json", auth="none", cors="*")
    def cambio(self, data):
        response = requests.request(
            "POST",
            f"{data.get('url','http://localhost')}:{data.get('port','8085')}/vpos/metodo",
            headers={
                "Content-Type": "application/json",
            },
            data=json.dumps(data.get("megasoft_data")),
            timeout=(5, None),
        )
        return response.json()

    @http.route(["/megasoft/pago"], type="json", auth="none", cors="*")
    def pago(self, data):
        response = requests.request(
            "POST",
            f"{data.get('url','http://localhost')}:{data.get('port','8085')}/vpos/metodo",
            headers={
                "Content-Type": "application/json",
            },
            data=json.dumps(data.get("megasoft_data")),
            timeout=(5, None),
        )
        return response.json()

    @http.route(["/megasoft/ultimaTransaccionAprobada"], type="json", auth="none", cors="*")
    def ultimaTransaccionAprobada(self, data):
        response = requests.request(
            "POST",
            f"{data.get('url','http://localhost')}:{data.get('port','8085')}/vpos/metodo",
            headers={
                "Content-Type": "application/json",
            },
            data=json.dumps(data.get("megasoft_data")),
            timeout=(5, None),
        )
        return response.json()

    @http.route(["/megasoft/ultimaTransaccionProcesada"], type="json", auth="none", cors="*")
    def ultimaTransaccionProcesada(self, data):
        response = requests.request(
            "POST",
            f"{data.get('url','http://localhost')}:{data.get('port','8085')}/vpos/metodo",
            headers={
                "Content-Type": "application/json",
            },
            data=json.dumps(data.get("megasoft_data")),
            timeout=(5, None),
        )
        return response.json()

    @http.route(["/megasoft/cierre"], type="json", auth="none", cors="*")
    def cierre(self, data):
        response = requests.request(
            "POST",
            f"{data.get('url','http://localhost')}:{data.get('port','8085')}/vpos/metodo",
            headers={
                "Content-Type": "application/json",
            },
            data=json.dumps(data.get("megasoft_data")),
            timeout=(5, None),
        )
        return response.json()
