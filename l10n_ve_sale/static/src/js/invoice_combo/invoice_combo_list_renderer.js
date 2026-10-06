/**
 * Extiende ProductLabelSectionAndNoteListRender (el list renderer de
 * invoice_line_ids) para:
 *
 * 1. Mostrar el subtotal correcto en las secciones/subsecciones de un combo
 *    (solo sumando las líneas marcadas con combo_tagged, no por posición).
 *
 * 2. Bloquear el arrastre (drag & drop) de filas que pertenezcan a un combo
 *    para que la jerarquía no se corrompa.
 *
 * Usa los mismos principios que combo_section_subtotal.js y
 * combo_lock_drag.js, adaptados para el renderer de facturas.
 */
import { patch } from '@web/core/utils/patch';
import { registry } from '@web/core/registry';
import { getSectionRecords } from '@account/components/section_and_note_fields_backend/section_and_note_fields_backend';
import { ProductLabelSectionAndNoteListRender } from '@account/components/product_label_section_and_note_field/product_label_section_and_note_field_o2m';

// ---------------------------------------------------------------------------
// Subtotal de sección filtrado por combo_tagged
// ---------------------------------------------------------------------------

patch(ProductLabelSectionAndNoteListRender.prototype, {
    /**
     * Para secciones/subsecciones que pertenecen a un combo, calcula el
     * subtotal sumando SOLO las líneas también marcadas como combo_tagged, en
     * vez de sumar todo lo que queda entre esta sección y la siguiente
     * (criterio posicional del nativo).
     */
    getFormattedValue(column, record) {
        if (
            this.isSection(record) &&
            this.props.aggregatedFields?.includes(column.name) &&
            record.data.combo_tagged
        ) {
            const total = getSectionRecords(this.props.list, record)
                .filter((r) => !this.isSection(r))
                .filter((r) => r.data.combo_tagged)
                .reduce((sum, r) => sum + (r.data[column.name] || 0), 0);

            const formatter = registry.category('formatters').get(column.fieldType, (val) => val);
            return formatter(total, {
                ...formatter.extractOptions?.(column),
                data: record.data,
                field: record.fields[column.name],
            });
        }
        return super.getFormattedValue(column, record);
    },

    // -------------------------------------------------------------------------
    // Lock de arrastre para filas de combo
    // -------------------------------------------------------------------------

    isComboLockedRowInvoice(record) {
        return Boolean(
            record.data.combo_tagged
            || record.data.display_type === 'line_subsection'
        );
    },

    getRowClass(record) {
        let classNames = super.getRowClass(record);
        if (this.isComboLockedRowInvoice(record)) {
            classNames = classNames.replace('o_row_draggable', '').trim();
        }
        const dt = record.data.display_type;
        if (dt === 'line_subsection') {
            classNames += ' l10n-ve-combo-subsection';
        } else if (record.data.combo_tagged && !this.isSection(record)) {
            classNames += ' l10n-ve-combo-item';
        }
        return classNames;
    },

    async sortDrop(dataRowId, dataGroupId, params) {
        const records = this.props.list.records;
        const draggedRecord = records.find((r) => r.id === dataRowId);
        const refId = params.previous ? params.previous.dataset.id : null;
        const targetRecord = refId ? records.find((r) => r.id === refId) : null;

        const touchesComboRow =
            (draggedRecord && this.isComboLockedRowInvoice(draggedRecord)) ||
            (targetRecord && this.isComboLockedRowInvoice(targetRecord));

        if (touchesComboRow) {
            params.element.classList.add('o_row_draggable');
            return;
        }
        return super.sortDrop(dataRowId, dataGroupId, params);
    },

    displayDeleteIcon(record) {
        const rootModel = this.props.list.model.root.resModel;
        // Solo ocultar el icono basura en filas de producto combo (no en
        // secciones/subsecciones: su eliminación va por el kebab).
        if (rootModel === 'account.move' && this.isComboLockedRowInvoice(record) && !this.isSection(record)) {
            return false;
        }
        return super.displayDeleteIcon(record);
    },
});

// Redirige ProductLabelSectionAndNoteListRender al template con soporte de
// combo. SaleOrderLineListRenderer NO se ve afectado: define su propio
// static recordRowTemplate = 'sale.ListRenderer.RecordRow'.
ProductLabelSectionAndNoteListRender.recordRowTemplate = 'l10n_ve_sale.InvoiceComboRecordRow';
