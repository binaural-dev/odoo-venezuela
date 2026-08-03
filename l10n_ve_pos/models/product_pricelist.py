import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Campos de ``product.pricelist.item`` cuyo valor es un monto ABSOLUTO en la
# moneda de la lista (a diferencia de los porcentuales, que son invariantes de
# escala). Ver ``_pos_warn_absolute_amounts_in_chain``.
_ABSOLUTE_AMOUNT_FIELDS = (
    "price_surcharge",
    "price_round",
    "price_min_margin",
    "price_max_margin",
)


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    # -----------------------------------------------------------------------
    # Carga de listas de precios ENCADENADAS en el PdV (Venezuela)
    # -----------------------------------------------------------------------
    #
    # PROBLEMA QUE RESUELVE:
    #   El core (``point_of_sale/models/product_pricelist.py`` ::
    #   ``_load_pos_data_domain``) resuelve las listas base UN SOLO NIVEL:
    #   busca los items con ``base='pricelist'`` de las listas *disponibles*
    #   en la caja y agrega sus ``base_pricelist_id``. Si esa lista base a su
    #   vez se ancla en otra, el tercer eslabón nunca se carga.
    #
    #   El patrón venezolano habitual es exactamente una cadena de 2+ niveles:
    #   la lista operativa en Bs se ancla a una lista de referencia en divisa
    #   (a veces con una intermedia), y los precios fijos viven SOLO en la
    #   lista en divisa. Es la forma de no reescribir el catálogo cada vez que
    #   se mueve la tasa BCV.
    #
    #   Cuando falta un eslabón, ``rule.base_pricelist_id`` llega vacío al
    #   navegador y ``getPrice()``
    #   (``point_of_sale/static/src/app/models/accounting/product_template_accounting.js``)
    #   cae a ``list_price`` sin avisar: el ``if (rule.base_pricelist_id)``
    #   interno corta antes de llamar a la recursión, así que tampoco salta el
    #   alert "Make sure all pricelists are available in the POS" del core.
    #   El cajero ve el precio del producto en vez del precio de la lista, y
    #   como suele ser el mismo placeholder en todo el catálogo, se ve un
    #   precio uniforme y obviamente equivocado.
    #
    #   OJO: el cálculo del core en JS es correcto — convierte hacia la moneda
    #   de la lista antes de aplicar la regla y de vuelta a la moneda del PdV
    #   después, así que las cadenas entre monedas dan el mismo número que el
    #   servidor. El defecto está únicamente en QUÉ se carga, no en cómo se
    #   calcula. No parchear ``getPrice``.
    #
    # KEEP IN SYNC WITH:
    #   ``models/pos_session.py`` ::
    #   ``get_pos_ui_product_pricelist_item_by_product`` — la carga on-demand
    #   de productos debe cubrir las mismas listas que la carga inicial, o los
    #   productos que entran por búsqueda se quedan sin precio fijo.

    @api.model
    def _pos_expand_base_pricelists(self, pricelist_ids):
        """Cierre transitivo de ``pricelist_ids`` siguiendo ``base='pricelist'``.

        Devuelve un ``set`` que incluye las listas de entrada más todas las
        listas base alcanzables, a cualquier profundidad.

        El guard ``seen`` es defensa en profundidad: ``product.pricelist.item``
        ya impide ciclos con ``_check_pricelist_recursion``, así que un ciclo no
        debería existir en base. Pero si llegara uno (datos cargados por SQL
        saltándose el ORM), el bucle termina en vez de colgar la apertura de la
        caja.
        """
        seen = set(pricelist_ids)
        pending = set(seen)
        item_model = self.env["product.pricelist.item"]
        while pending:
            found = item_model.search(
                [
                    ("pricelist_id", "in", list(pending)),
                    ("base", "=", "pricelist"),
                    ("base_pricelist_id", "!=", False),
                ]
            ).base_pricelist_id.ids
            pending = set(found) - seen
            seen |= pending
        return seen

    @api.model
    def _load_pos_data_domain(self, data, config):
        """Extiende el dominio del core al cierre transitivo de la cadena.

        Se ejecuta el dominio del core con ``search`` en vez de inspeccionar su
        forma: así seguimos siendo correctos si el core cambia cómo arma la
        semilla (listas disponibles, presets, etc.).
        """
        domain = super()._load_pos_data_domain(data, config)
        seed = self.search(domain).ids
        chain = self._pos_expand_base_pricelists(seed)
        self._pos_warn_absolute_amounts_in_chain(set(chain) - set(seed))
        return [("id", "in", list(chain))]

    @api.model
    def _pos_warn_absolute_amounts_in_chain(self, base_pricelist_ids):
        """Avisa si una lista base usa montos absolutos en su moneda.

        ``models/res_currency.py`` restringe a propósito las monedas que viajan
        al PdV (compañía + moneda del PdV + divisa), así que la moneda de una
        lista intermedia normalmente NO se carga. En ``getPrice()`` eso hace
        que ``needsCurrencyConversion`` sea falso y se salten AMBAS
        conversiones de ese nivel.

        Para reglas porcentuales da igual: son invariantes de escala y las dos
        conversiones son inversas exactas, así que el resultado no cambia (caso
        verificado: cadena Bs → EUR → USD con solo VEF y USD cargadas da el
        mismo número que el servidor).

        Pero ``price_surcharge`` y compañía son montos absolutos en la moneda
        de la lista: sin conversión se suman en la escala equivocada. Preferimos
        avisar antes que devolver un precio plausible y falso.
        """
        if not base_pricelist_ids:
            return
        risky = self.env["product.pricelist.item"].search(
            [
                ("pricelist_id", "in", list(base_pricelist_ids)),
                "|",
                "|",
                ("price_surcharge", "!=", 0),
                ("price_round", "!=", 0),
                "|",
                ("price_min_margin", "!=", 0),
                ("price_max_margin", "!=", 0),
            ]
        )
        if not risky:
            return
        _logger.warning(
            "PdV: las listas de precios base %s usan montos absolutos (%s) en su "
            "propia moneda, pero l10n_ve_pos no carga esa moneda en la caja. "
            "El PdV puede mostrar un precio distinto al del servidor. "
            "Usa reglas porcentuales en las listas intermedias de la cadena.",
            risky.pricelist_id.mapped("display_name"),
            ", ".join(_ABSOLUTE_AMOUNT_FIELDS),
        )
