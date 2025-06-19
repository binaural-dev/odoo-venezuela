import json
import logging
from datetime import datetime
from collections import OrderedDict
from werkzeug.exceptions import Forbidden, NotFound

from odoo import _, http
from odoo.http import request
from odoo.osv import expression
from odoo.addons.portal.controllers.portal import pager as agro_pager
from odoo.addons.binaural_farming_website.controllers.main_agro import MainAgro


_logger = logging.getLogger(__name__)


class CadipaAgro(MainAgro):

    @http.route(
        [
            "/agro/<string:service>/<string:specie>/<string:race_animal>/<string:gender>",
            "/agro/<string:service>/<string:specie>/<string:race_animal>/<string:gender>/page/<int:page>",
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
        gender=None,
        specie=None,
        lot=None,
        lot_id=None,
        page=1,
        search=None,
        search_in="name",
        url="/agro",
        **kw,
    ):
        """
        Esto fue personalizado ya que con las urls se estructuraran el uso de codigos QR personalizados
        para la lista de los animales y para llegarles a los animales

        Args:
            service (str, optional): _description_. Defaults to None.
            race_animal (str, optional): Raza del animal. Defaults to None.
            gender (str, optional): Genero del animal. Defaults to None.
            specie (str, optional): Especie del animal. Defaults to None.
            lot (str, optional): Nombre del Lote. Defaults to None.
            lot_id (int, optional): id del lote. Defaults to None.
            page (int, optional): Paginador. Defaults to 1.
            search (str, optional): Texto del buscador. Defaults to None.
            search_in (str, optional): Tipo de busqueda. Defaults to "name".
            url (str, optional):  Defaults to "/agro".

        Returns:
            HTML: Pagina principal de los animales o pagina del animal
        """
        if not lot and not lot_id:
            _items_per_page = 15
            domain = self.domain_lots()
            url_service = url + f"/{service}"
            url = self._build_url_agro(url, service, race_animal, specie, gender)

            if gender and gender == "sementales":
                domain = expression.AND([domain, [("gender", "=", "male")]])
            elif gender and gender == "reproductoras":
                domain = expression.AND([domain, [("gender", "=", "female")]])

            if specie:
                domain = expression.AND([domain, [("specie_id.name", "ilike", specie)]])

            if race_animal:
                domain = expression.AND(
                    [domain, [("lot_race_id.description", "ilike", race_animal)]]
                )

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

    def _build_url_agro(self, url, service, race_animal, specie, gender):
        if service:
            url += f"/{service}"
        if specie:
            url += f"/{specie}"
        if race_animal:
            url += f"/{race_animal}"
        if gender:
            url += f"/{gender}"
        return url
