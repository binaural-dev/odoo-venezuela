import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

/**
 * "Mostrar solamente los productos disponibles": el servidor no carga los
 * almacenables sin stock, pero las opciones de combo llegan igual, con
 * self_order_available = false (models/product_template.py). El core las
 * pintaría en la cuadrícula como "Agotado"; con el ajuste no se muestran.
 * Dentro del combo siguen como agotadas y el escaneo responde "no
 * disponible".
 *
 * The POS special products (tips, service charge, discount, down payment,
 * default product) are never shown either. Core 20 loads them in the Kiosk
 * (tips and the service charge are used at payment) and hides them only by the
 * flag of the variant, which the self-order load does not send; the flag of
 * the template does arrive. Odoo 19 did not load them.
 */
export function isShownInCatalog(config, productTemplate) {
    if (productTemplate._is_pos_special_product) {
        return false;
    }
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
