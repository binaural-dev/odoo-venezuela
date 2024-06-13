import json
import logging
from datetime import datetime

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.portal.controllers.portal import pager as agro_pager


_logger = logging.getLogger(__name__)


class MainAgro(http.Controller):

    @http.route(
        ["/agro", "/agro/page/<int:page>", "/agro/<string:lot>"],
        type="http",
        auth="public",
        website=True,
    )
    def website_agro(self, lot=None, page=1, search=None, search_in="name", url="/agro", **kw):
        if not lot:
            _items_per_page = 15
            domain = self.domain_lots()
            lot_count = request.env["stock.lot"].search_count(domain)

            pager = agro_pager(
                url=url,
                url_args={
                    "search_in": search_in,
                    "search": search,
                },
                total=lot_count,
                page=page,
                step=_items_per_page,
            )
            if search and search_in:
                domain = expression.AND([domain, self._get_search_domain_lots(search_in, search)])
            lot_ids = request.env["stock.lot"].search(
                domain, limit=_items_per_page, offset=pager["offset"]
            )
            return request.render(
                "binaural_farming_website.main_agro_template",
                {
                    "search": search,
                    "search_in": search_in,
                    "default_url": url,
                    "searchbar_inputs": self._get_searchbar_inputs_lots(),
                    "pager": pager,
                    "lots": lot_ids,
                },
            )
        lot_id = request.env["stock.lot"].search([("name", "=", lot)])

        return request.render(
            "binaural_farming_website.agro_animal_lot",
            {
                "lot": lot_id,
            },
        )

    def _get_searchbar_inputs_lots(self):
        return {
            "name": {"input": "name", "label": _("Search for Lot")},
            "race": {"input": "race", "label": _("Search for Race")},
        }

    def _get_search_domain_lots(self, search_in, search):
        search_domain = []
        if search_in == "name":
            search_domain = expression.OR([search_domain, [("name", "ilike", search)]])
        if search_in == "race":
            search_domain = expression.OR(
                [search_domain, [("lot_race_id.description", "ilike", search)]]
            )
        return search_domain

    def domain_lots(self):
        website = request.env["website"].get_current_website()
        website_company_id = website._get_cached("company_id")
        return [("gender", "!=", False), ("company_id", "in", [False, website_company_id])]
