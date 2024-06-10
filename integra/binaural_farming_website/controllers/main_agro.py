import json
import logging
from datetime import datetime

from odoo import _, http
from odoo.http import request
from odoo.osv import expression


_logger = logging.getLogger(__name__)

class MainAgro(http.Controller):

    @http.route(
        ["/agro","/agro/<int:lot>"], type="http", auth="public", website=True
    )
    def website_agro(self, lot=None, **kw):
        # lot= 1
        if not lot:

            return request.render(
                "binaural_farming_website.main_agro_template",{},
            )
        return request.render(
            "binaural_farming_website.agro_animal_lot",{
            },
        )
    