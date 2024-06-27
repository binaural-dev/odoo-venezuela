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
            "/agro/ganaderia",
            "/agro/ganaderia/page/<int:page>",
            "/agro/ganaderia/<string:specie>",
            "/agro/ganaderia/<string:specie>/page/<int:page>",
            "/agro/ganaderia/<string:specie>/<string:lot>-<int:lot_id>",
            "/agro/ganaderia/<string:lot>-<int:lot_id>",
        ],
        type="http",
        auth="public",
        website=True,
    )
    def website_agro(
        self,
        lot=None,
        lot_id=None,
        specie=None,
        page=1,
        filterby=None,
        search=None,
        search_in="name",
        url="/agro/ganaderia",
        **kw
    ):
        if not lot and not lot_id:
            _items_per_page = 15
            domain = self.domain_lots()

            searchbar_filters = self._get_searchbar_filters()
            if not filterby:
                filterby = "all"
            domain = expression.AND([domain, searchbar_filters[filterby]["domain"]])

            if specie:
                domain = expression.AND([domain, [("specie_id.name", "=", specie)]])

            if search and search_in:
                domain = expression.AND([domain, self._get_search_domain_lots(search_in, search)])

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
                    "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                    "filterby": filterby,
                    "lots": lot_ids,
                },
            )
        lot_id = request.env["stock.lot"].browse(lot_id)
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
        specie_ids = request.env["stock.specie"].search([])
        for specie in specie_ids:
            filter_records[specie.name] = {
                "label": specie.name,
                "domain": [("specie_id", "=", specie.id)],
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
