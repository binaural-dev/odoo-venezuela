import { patch } from '@web/core/utils/patch';
import { SaleOrderLineProductField } from '@sale/js/sale_product_field';

// El nativo (`m2oProps`, ver sale_product_field.js) le agrega
// " x <cantidad>" al nombre mostrado del producto SOLO para la línea real
// del combo ("combooo x 1"), puramente visual (no toca `name` ni
// `product_id.display_name` en la base). Se llama a `super.m2oProps`
// (conserva el resto de lo que hace esa misma línea: canOpen, el
// wrapping de `update`, etc.) y se le quita ese sufijo si lo trae.
patch(SaleOrderLineProductField.prototype, {
    get m2oProps() {
        const p = super.m2oProps;
        if (this.isCombo && p.value && p.value.display_name) {
            const qtySuffix = ` x ${this.props.record.data.product_uom_qty}`;
            let name = p.value.display_name.endsWith(qtySuffix)
                ? p.value.display_name.slice(0, -qtySuffix.length)
                : p.value.display_name;
            p.value = { ...p.value, display_name: name.toUpperCase() };
        }
        return p;
    },
});
