import json
import logging
from datetime import datetime

from odoo import _, http
from odoo.http import request
from odoo.osv import expression


_logger = logging.getLogger(__name__)

class MainAgro(http.Controller):

    @http.route(
        ["/agro","/agro/<string:lot>"], type="http", auth="public", website=True
    )
    def website_agro(self, lot=None, **kw):
        if not lot:
            lot_ids = request.env["stock.lot"].search([('gender', '!=', False)])
            return request.render(
                "binaural_farming_website.main_agro_template",
                {
                    "lots": lot_ids
                },
            )
        lot_id = request.env["stock.lot"].search([('name', '=', lot)])
        
        return request.render(
            "binaural_farming_website.agro_animal_lot",
            {
                "lot": lot_id,
            },
        )
    