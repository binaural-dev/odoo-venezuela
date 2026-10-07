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
        // Solo filas realmente de combo: una subsección nativa del usuario
        // (sin combo_tagged ni combo_parent_line_id) sigue siendo movible.
        return Boolean(
            this.isCombo(record)
            || this.isComboItem(record)
            || record.data.combo_tagged
            || (this.isSection(record) && record.data.combo_parent_line_id)
        );
    },

    getRowClass(record) {
        let classNames = super.getRowClass(record);
        if (this.isComboLockedRow(record)) {
            classNames = classNames.replace('o_row_draggable', '').trim();
        }
        if (this.isSection(record)) {
            if (record.data.combo_tagged || record.data.combo_parent_line_id) {
                classNames += ' l10n-ve-combo-subsection';
            }
        } else if (!this.isCombo(record) && (
            record.data.combo_tagged
            || this.isComboItem(record)
            || record.data.combo_parent_line_id
        )) {
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
