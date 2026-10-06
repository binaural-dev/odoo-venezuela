/**
 * Dispara el ComboConfiguratorDialog en facturas (account.move) cuando el
 * usuario elige un producto de tipo "combo" en una línea de factura.
 *
 * Parcha ProductLabelSectionAndNoteField — el widget que usa invoice_line_ids
 * (widget="product_label_section_and_note_field").
 *
 * NOTA: ProductLabelSectionAndNoteField NO define `this.value`; el acceso al
 * producto es `this.props.record.data[this.props.name]`. Usar `this.value` (como
 * hace SaleOrderLineProductField, que sí lo define) devuelve `undefined` y el
 * useEffect nunca se dispara.
 */
import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { useEffect } from '@odoo/owl';
import { rpc } from '@web/core/network/rpc';
import { serializeDateTime, today } from '@web/core/l10n/dates';

import { ProductLabelSectionAndNoteField } from '@account/components/product_label_section_and_note_field/product_label_section_and_note_field';
import { ComboConfiguratorDialog } from '@sale/js/combo_configurator_dialog/combo_configurator_dialog';
import { ProductCombo } from '@sale/js/models/product_combo';
import { serializeComboItem } from '@sale/js/sale_utils';

patch(ProductLabelSectionAndNoteField.prototype, {
    setup() {
        super.setup(...arguments);

        const rootModel = this.props.record.model.root.resModel;
        if (rootModel !== 'account.move') {
            return;
        }

        this._invoiceComboIsInternalUpdate = false;
        this._invoiceComboDialog = useService('dialog');
        this._invoiceComboOrm = useService('orm');

        let isMounted = false;
        useEffect(
            (productId) => {
                if (!isMounted) {
                    isMounted = true;
                    return;
                }
                if (!productId || !this._invoiceComboIsInternalUpdate) {
                    this._invoiceComboIsInternalUpdate = false;
                    return;
                }
                this._invoiceComboIsInternalUpdate = false;
                // record.data.product_type es stale aquí: el onchange que lo
                // actualiza (async) todavía no completó cuando el useEffect dispara.
                // Se lee el tipo directo vía ORM, igual que sale lee is_combo
                // desde get_single_product_variant antes de abrir el configurador.
                this._invoiceComboOrm
                    .read('product.product', [productId], ['type'])
                    .then(([product]) => {
                        if (product?.type === 'combo') {
                            this._openComboConfiguratorInvoice(false);
                        }
                    });
            },
            // ProductLabelSectionAndNoteField NO tiene `this.value` — el producto
            // vive en this.props.record.data[this.props.name].
            () => [this.props.record.data[this.props.name]?.id]
        );
    },

    /**
     * Override m2oProps para saber cuándo el usuario elige un producto
     * interactivamente (vs. actualizaciones de onchanges externos).
     */
    get m2oProps() {
        const p = super.m2oProps;
        const rootModel = this.props.record.model.root.resModel;
        if (rootModel !== 'account.move') return p;
        return {
            ...p,
            update: (value) => {
                this._invoiceComboIsInternalUpdate = true;
                return p.update(value);
            },
        };
    },

    /**
     * Abre el ComboConfiguratorDialog para una línea de factura.
     * @param {boolean} edit - true al re-editar un combo ya configurado.
     */
    async _openComboConfiguratorInvoice(edit = false) {
        const invoice = this.props.record.model.root.data;
        const comboLineRecord = this.props.record;

        // product_template_id es un campo related cargado en la vista; si aún
        // no está resuelto se hace una llamada ORM como fallback.
        const productTmplId =
            comboLineRecord.data.product_template_id?.id ||
            (comboLineRecord.data.product_id?.id &&
                (await rpc('/web/dataset/call_kw', {
                    model: 'product.product',
                    method: 'read',
                    args: [[comboLineRecord.data.product_id.id], ['product_tmpl_id']],
                    kwargs: {},
                }))[0]?.product_tmpl_id?.[0]);

        // date es requerido en ComboConfiguratorDialog (type: String, sin optional).
        // Usar hoy como fallback cuando la factura aún no tiene fecha.
        const date = serializeDateTime(invoice.invoice_date || today());

        const { combos, ...remainingData } = await rpc('/sale/combo_configurator/get_data', {
            product_tmpl_id: productTmplId,
            currency_id:
                comboLineRecord.data.currency_id?.id ||
                invoice.currency_id?.id,
            quantity: comboLineRecord.data.quantity || 1,
            date,
            company_id: invoice.company_id.id,
            selected_combo_items: [],
            // pricelist_id omitido — optional: true; pasar false o null falla
            // la validación de props (type: Number, no acepta booleanos).
        });

        const comboChoices = combos.map((combo) => new ProductCombo(combo));
        const preselectedItems = comboChoices
            .map((c) => c.preselectedComboItem)
            .filter(Boolean);

        if (preselectedItems.length === comboChoices.length) {
            return this._handleComboSaveInvoice(
                { quantity: remainingData.quantity },
                preselectedItems,
                edit
            );
        }

        this._invoiceComboDialog.add(ComboConfiguratorDialog, {
            combos: comboChoices,
            ...remainingData,
            date: remainingData.date || date,
            company_id: invoice.company_id.id,
            // pricelist_id: no se pasa (opcional, undefined es válido)
            edit,
            save: async (comboProductData, selectedComboItems) => {
                this._handleComboSaveInvoice(
                    comboProductData,
                    selectedComboItems,
                    edit
                );
            },
            discard: () => invoice.invoice_line_ids.delete(comboLineRecord),
        });
    },

    /**
     * Maneja el resultado del configurador: escribe selected_combo_items en la
     * línea para que el onchange Python cree las sublíneas.
     */
    async _handleComboSaveInvoice(comboProductData, selectedComboItems, edit) {
        const invoice = this.props.record.model.root.data;
        const comboLineRecord = this.props.record;
        invoice.invoice_line_ids.leaveEditMode();
        const comboLineValues = {
            quantity: comboProductData.quantity,
            selected_combo_items: JSON.stringify(
                selectedComboItems.map((item) => ({
                    ...serializeComboItem(item),
                    quantity: item.quantity || 1,
                }))
            ),
        };
        await comboLineRecord.update(comboLineValues);
        await invoice.invoice_line_ids._sort();
    },
});
