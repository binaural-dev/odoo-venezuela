/** @odoo-module */

import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { patch } from "@web/core/utils/patch";

patch(ProductTemplate.prototype, {
    // "Mostrar solamente los productos disponibles": la cuadrícula oculta los
    // productos almacenables sin stock a mano en el almacén de la caja (el
    // qty_available de las variantes, que product_product.py carga con ese
    // almacén). En O19 la cuadrícula y la búsqueda solo filtran por
    // canBeDisplayed (PosStore.filterExcludedProducts); el escaneo de código
    // de barras no pasa por aquí.
    get canBeDisplayed() {
        if (!super.canBeDisplayed) {
            return false;
        }
        const config = this.models["pos.config"].getFirst();
        if (!config?.pos_show_just_products_with_available_qty || !this.is_storable) {
            return true;
        }
        return this.product_variant_ids.some((variant) => variant.qty_available > 0);
    },
});
