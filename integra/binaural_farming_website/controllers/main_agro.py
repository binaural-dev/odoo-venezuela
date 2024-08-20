import json
import logging
from datetime import datetime
from collections import OrderedDict
from werkzeug.exceptions import Forbidden, NotFound

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.portal.controllers.portal import pager as agro_pager


_logger = logging.getLogger(__name__)


class MainAgro(http.Controller):

    @http.route(
        [
            "/agro/<string:service>/<string:specie>/<string:race_animal>",
            "/agro/<string:service>/<string:specie>/<string:race_animal>/page/<int:page>",
            "/agro/<string:service>/<string:lot>-<int:lot_id>",
        ],
        type="http",
        auth="public",
        website=True,
    )
    def website_agro(
        self,
        service=None,
        race_animal=None,
        specie=None,
        lot=None,
        lot_id=None,
        page=1,
        filterby=None,
        search=None,
        search_in="name",
        url="/agro",
        **kw
    ):
        if not lot and not lot_id:
            _items_per_page = 15
            domain = self.domain_lots()
            url_service = url + f"/{service}"
            url = self._build_url_agro(url, service, race_animal, specie)

            searchbar_filters = self._get_searchbar_filters()
            if not filterby:
                filterby = "all"
            domain = expression.AND([domain, searchbar_filters[filterby]["domain"]])

            if specie:
                domain = expression.AND([domain, [("specie_id.name", "ilike", specie)]])

            if race_animal:
                domain = expression.AND([domain, [("lot_race_id.description", "ilike", race_animal)]])

            if search and search_in:
                domain = expression.AND([domain, self._get_search_domain_lots(search_in, search)])
            
            lot_count = request.env["stock.lot"].sudo().search_count(domain)

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

            lot_ids = request.env["stock.lot"].sudo().search(
                domain, limit=_items_per_page, offset=pager["offset"]
            )
            return request.render(
                "binaural_farming_website.main_agro_template",
                {
                    "search": search,
                    "search_in": search_in,
                    "default_url": url,
                    "url_service": url_service,
                    "searchbar_inputs": self._get_searchbar_inputs_lots(),
                    "pager": pager,
                    "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                    "filterby": filterby,
                    "lots": lot_ids,
                },
            )
        
        if service:
            url += f"/{service}"
        lot_id = request.env["stock.lot"].sudo().browse(lot_id)
        if not lot_id:
            raise NotFound()

        return request.render(
            "binaural_farming_website.agro_animal_lot",
            {
                "default_url": url,
                "lot": lot_id,
            },
        )

    def _get_searchbar_inputs_lots(self):
        return {
            "name": {"input": "name", "label": _("Search for Lot")},
            "race": {"input": "race", "label": _("Search for Race")},
        }

    def _get_searchbar_filters(self):
        filter_records = {
            "all": {"label": _("All"), "domain": []},
            "female": {
                "label": _("Female"),
                "domain": [("gender", "=", "female")],
            },
            "male": {
                "label": _("Male"),
                "domain": [("gender", "=", "male")],
            },
        }

        return filter_records

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
        return [
            ("gender", "!=", False),
            ("company_id", "in", [False, website_company_id]),
            ("publishing_on_the_web", "=", True),
        ]
    
    def _build_url_agro(self, url, service, race_animal, specie):
        if service:
            url += f"/{service}"
        if specie:
            url += f"/{specie}"
        if race_animal:
            url += f"/{race_animal}"
        return url
