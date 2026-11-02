import { patch } from "@web/core/utils/patch";
import { PosCategory } from "@point_of_sale/app/models/pos_category";
import { isShownInCatalog } from "@l10n_ve_pos_self_order/overrides/self_order_service";

patch(PosCategory.prototype, {
    // La cuadrícula del Kiosko pide los productos de cada categoría real a
    // este getter (ProductListPage.getProducts) y oculta la pestaña de una
    // categoría que se queda sin ellos (SelfOrder.getAvailableCategories):
    // mismo filtro que la categoría "Sin categoría" (overrides/self_order_service.js).
    // Solo entra en el bundle del Kiosko.
    get associatedProducts() {
        const config = this.models["pos.config"]?.getFirst();
        return super.associatedProducts.filter((productTemplate) =>
            isShownInCatalog(config, productTemplate)
        );
    },
});
