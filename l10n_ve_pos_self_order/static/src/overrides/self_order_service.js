import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

/**
 * "Mostrar solamente los productos disponibles": el servidor no carga los
 * almacenables sin stock, pero las opciones de combo llegan igual, con
 * self_order_available = false (models/product_template.py). El core las
 * pintaría en la cuadrícula como "Agotado"; con el ajuste no se muestran.
 * Dentro del combo siguen como agotadas y el escaneo responde "no
 * disponible".
 */
export function isShownInCatalog(config, productTemplate) {
    return (
        !config?.pos_show_just_products_with_available_qty ||
        productTemplate.self_order_available ||
        !productTemplate.is_storable
    );
}

patch(SelfOrder.prototype, {
    // La categoría sintética "Sin categoría" sale de productByCategIds; las
    // categorías reales, de PosCategory.associatedProducts
    // (overrides/pos_category.js).
    initProducts() {
        super.initProducts(...arguments);
        for (const categoryId in this.productByCategIds) {
            this.productByCategIds[categoryId] = this.productByCategIds[categoryId].filter(
                (productTemplate) => isShownInCatalog(this.config, productTemplate)
            );
        }
    },
});
