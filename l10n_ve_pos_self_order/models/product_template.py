from odoo import api, models
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _pos_self_available_qty_domain(self, config):
        """Plantillas que el autopedido (Kiosko y móvil) puede ofrecer con
        "Mostrar solamente los productos disponibles"
        (``pos_show_just_products_with_available_qty``): lo no almacenable y
        los almacenables con alguna variante con stock a mano positivo en la
        ubicación de origen de la caja y sus hijas, la misma cantidad con la
        que filtra la caja (``l10n_ve_pos``,
        ``product.product._load_pos_data_read``).
        """
        variants = self.env["product.product"]
        location = config.picking_type_id.default_location_src_id
        if location:
            variants = variants.with_context(location=location.id)
        in_stock = variants._search([("qty_available", ">", 0)])
        return ["|", ("is_storable", "=", False), ("product_variant_ids", "in", in_stock)]

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        """El autopedido no pasa por el ``canBeDisplayed`` de la caja: arma la
        cuadrícula, el buscador de "solo escaneo / búsqueda" y el escaneo con
        todo lo que carga, así que con el ajuste el almacenable sin stock se
        deja fuera de la carga (como el core con ``self_order_available``). El
        tope de productos cargados cuenta entonces solo lo que se puede vender.
        El Kiosko no guarda caché en el navegador: cada carga de la página lee
        el stock actual.
        """
        domain = super()._load_pos_self_data_domain(data, config)
        if not config.pos_show_just_products_with_available_qty:
            return domain
        return Domain.AND([domain, self._pos_self_available_qty_domain(config)])

    @api.model
    def _load_pos_self_data_read(self, data, config):
        """Las opciones de los combos las agrega el core por id, sin pasar por
        ``_load_pos_self_data_domain``: con el ajuste, las almacenables sin
        stock llegan con ``self_order_available = False``. El core entonces no
        deja elegirlas en el combo y responde "no disponible" al escanearlas;
        el buscador de "solo escaneo / búsqueda" ya las salta y
        ``static/src/overrides/self_order_service.js`` las saca de la
        cuadrícula.
        """
        products = super()._load_pos_self_data_read(data, config)
        if not config.pos_show_just_products_with_available_qty:
            return products
        available_ids = set(
            self.search(
                Domain.AND([
                    [("id", "in", [product["id"] for product in products])],
                    self._pos_self_available_qty_domain(config),
                ])
            ).ids
        )
        for product in products:
            if product["id"] not in available_ids:
                product["self_order_available"] = False
        return products
