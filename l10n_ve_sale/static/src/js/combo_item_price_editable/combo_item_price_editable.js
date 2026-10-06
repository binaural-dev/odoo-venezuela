import { SaleOrderLineListRenderer } from '@sale/js/sale_order_line_field/sale_order_line_field';
import { patch } from '@web/core/utils/patch';

// El precio de un ítem de combo normalmente es readonly (ver
// `isCellReadonly` nativo, que solo deja editar `name`/`tax_ids`/
// `qty_delivered`) porque nativamente se recalcula solo vía el
// prorrateo de `_get_combo_item_display_price`. Acá ese prorrateo ya no
// es automático para los ítems `fixed_price`/`percentage`/`principal`
// (ver `item_type` en product_combo_item.py) -- se permite ajustar
// `price_unit` a mano cuando haga falta.
patch(SaleOrderLineListRenderer.prototype, {
    isCellReadonly(column, record) {
        if (this.isComboItem(record) && column.name === 'price_unit') {
            return false;
        }
        return super.isCellReadonly(column, record);
    },
});
