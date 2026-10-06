import { patch } from '@web/core/utils/patch';
import { uuid } from '@web/core/utils/strings';
import { ComboConfiguratorDialog } from '@sale/js/combo_configurator_dialog/combo_configurator_dialog';
import { SaleOrderLineProductField } from '@sale/js/sale_product_field';
import { serializeComboItem } from '@sale/js/sale_utils';

import { useState } from '@odoo/owl';

patch(ComboConfiguratorDialog.prototype, {
    setup() {
        super.setup(...arguments);
        // Garantizamos que esté instanciado en el state/componente
        if (!this.selectedQuantities) {
            this.selectedQuantities = useState(new Map());
        }
    },

    /**
     * Getter defensivo: verifica siempre si existe selectedQuantities
     */
    get selectedQuantitiesMap() {
        if (!this.selectedQuantities) {
            this.selectedQuantities = useState(new Map());
        }
        return this.selectedQuantities;
    },

    _initSelectedComboItems() {
        this.state.selectedComboItems = new Map();
        for (const combo of this.props.combos) {
            const comboItem = combo.selectedComboItem;
            if (comboItem) {
                this.selectedQuantitiesMap.set(comboItem.id, 1);
                this.state.selectedComboItems.set(comboItem.id, comboItem.deepCopy());
            }
        }
    },

    getItemQuantity(comboItemId) {
        return this.selectedQuantitiesMap.get(comboItemId) || 0;
    },

    updateItemQuantity(comboId, comboItem, delta) {
        const itemId = comboItem.id;
        const currentQty = this.getItemQuantity(itemId);
        const newQty = Math.max(0, currentQty + delta);

        if (newQty === 0) {
            this.selectedQuantitiesMap.delete(itemId);
            this.state.selectedComboItems.delete(itemId);
        } else {
            this.selectedQuantitiesMap.set(itemId, newQty);
            const itemToSelect = this.getSelectedOrProvidedComboItem(comboId, comboItem);
            this.state.selectedComboItems.set(itemId, itemToSelect.deepCopy());
        }

        this.state.selectedComboItems = new Map(this.state.selectedComboItems);
    },

    get areAllCombosSelected() {
        let totalCount = 0;
        const map = this.selectedQuantitiesMap;
        if (map && typeof map.values === 'function') {
            for (const qty of map.values()) {
                totalCount += qty;
            }
        }
        return totalCount > 0;
    },

    get _selectedComboItems() {
        const result = [];
        for (const combo of this.props.combos) {
            for (const item of combo.combo_items) {
                const qty = this.getItemQuantity(item.id);
                if (qty > 0) {
                    // Una sola línea por producto: la cantidad va adjunta
                    // (ver handleComboSave) en vez de repetir el item N
                    // veces, porque server-side debe crear UNA línea con
                    // product_uom_qty = qty, no N líneas de qty = 1.
                    const copy = this.getSelectedOrProvidedComboItem(combo.id, item).deepCopy();
                    copy.quantity = qty;
                    result.push(copy);
                }
            }
        }
        return result;
    },

    get _comboPrice() {
        let price = this.props.price || 0;
        for (const combo of this.props.combos) {
            for (const item of combo.combo_items) {
                const qty = this.getItemQuantity(item.id);
                if (qty > 0 && item.extra_price) {
                    price += item.extra_price * qty;
                }
            }
        }
        return price;
    },

    async confirm(options) {
        this.state.isLoading = true;

        Promise.resolve(
            this.props.save(
                { quantity: this.state.quantity },
                this._selectedComboItems,
                options
            )
        ).catch((err) => {
            console.error("Error al guardar combo:", err);
        }).finally(() => {
            this.state.isLoading = false;
            this.props.close();
        });
    }
});

// El core serializa cada item seleccionado vía `serializeComboItem`, que no
// lleva cantidad (siempre asume 1 producto por opción). Acá se inyecta la
// cantidad que el usuario eligió por producto (`item.quantity`, ver
// `_selectedComboItems` arriba) para que el onchange de Python pueda crear
// cada línea con su `product_uom_qty` real en vez de duplicar la línea.
patch(SaleOrderLineProductField.prototype, {
    async handleComboSave(comboProductData, selectedComboItems, edit, hasOptionalProducts) {
        const saleOrder = this.props.record.model.root.data;
        const comboLineRecord = this.props.record;
        saleOrder.order_line.leaveEditMode();
        const comboLineValues = {
            product_uom_qty: comboProductData.quantity,
            selected_combo_items: JSON.stringify(
                selectedComboItems.map(item => ({
                    ...serializeComboItem(item),
                    quantity: item.quantity || 1,
                }))
            ),
        };
        if (!edit) {
            comboLineValues.virtual_id = uuid();
        }
        await comboLineRecord.update(comboLineValues);
        // Ensure that the order lines are sorted according to their sequence.
        await saleOrder.order_line._sort();

        if (hasOptionalProducts && !edit) {
            const selectedComboProducts = selectedComboItems.map(
                item => ({ name: item.product.display_name })
            );
            await this._openProductConfigurator(false, selectedComboProducts);
        }
    },
});
