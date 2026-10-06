import { patch } from '@web/core/utils/patch';
import { SaleOrderLineListRenderer } from '@sale/js/sale_order_line_field/sale_order_line_field';

// Una vez creadas, las secciones/subsecciones del combo y sus productos no
// deben poder arrastrarse ni recibir un drop justo después de ellas: el
// `parent_id` nativo agrupa por POSICIÓN pura (ver
// `sale.order.line._compute_parent_id`), así que mover cualquiera de estas
// filas, o soltar una fila ajena entre ellas, corrompe la jerarquía del
// combo sin que el modelo se entere.
patch(SaleOrderLineListRenderer.prototype, {
    isComboLockedRow(record) {
        // combo_tagged y display_type son los flags primarios.
        // combo_parent_line_id permite detectar subsecciones en SOs guardados
        // con código anterior donde combo_tagged puede ser False.
        // isComboItem cubre ítems nativos del configurador de combo.
        return Boolean(
            this.isCombo(record)
            || this.isComboItem(record)
            || record.data.combo_tagged
            || record.data.display_type === 'line_subsection'
            || (this.isSection(record) && record.data.combo_parent_line_id)
        );
    },

    getRowClass(record) {
        let classNames = super.getRowClass(record);
        if (this.isComboLockedRow(record)) {
            classNames = classNames.replace('o_row_draggable', '').trim();
        }
        const dt = record.data.display_type;
        // Subsección: display_type='line_subsection' (datos nuevos) O
        // sección con combo_parent_line_id (datos guardados con código anterior
        // donde _retag promovió a line_section pero sí estableció el parent).
        const isComboSubsection =
            dt === 'line_subsection'
            || (this.isSection(record) && record.data.combo_parent_line_id);

        if (isComboSubsection) {
            classNames += ' l10n-ve-combo-subsection';
        } else if (!this.isCombo(record) && !this.isSection(record) && (
            record.data.combo_tagged
            || this.isComboItem(record)
            || record.data.combo_parent_line_id
        )) {
            // Productos hijo del combo: detectados por combo_tagged (datos nuevos),
            // isComboItem (ítems nativos del wizard), o combo_parent_line_id.
            classNames += ' l10n-ve-combo-item';
        }
        return classNames;
    },

    async sortDrop(dataRowId, dataGroupId, params) {
        const records = this.props.list.records;
        const draggedRecord = records.find((r) => r.id === dataRowId);
        const refId = params.previous ? params.previous.dataset.id : null;
        const targetRecord = refId ? records.find((r) => r.id === refId) : null;

        const touchesComboRow = (
            (draggedRecord && this.isComboLockedRow(draggedRecord))
            || (targetRecord && this.isComboLockedRow(targetRecord))
        );
        if (touchesComboRow) {
            // Barrera dura: no se llama a super() en absoluto, así no se
            // dispara ningún resequence para este drop.
            params.element.classList.add('o_row_draggable');
            return;
        }

        return super.sortDrop(dataRowId, dataGroupId, params);
    },
});
