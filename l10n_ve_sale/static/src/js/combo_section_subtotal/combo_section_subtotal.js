import { patch } from '@web/core/utils/patch';
import { registry } from '@web/core/registry';
import { getSectionRecords } from '@account/components/section_and_note_fields_backend/section_and_note_fields_backend';
import { SaleOrderLineListRenderer } from '@sale/js/sale_order_line_field/sale_order_line_field';

// El total de una sección/subsección de combo y del combo raíz se calcula
// filtrando SOLO las líneas marcadas con combo_tagged, en vez de confiar en
// posición o en combo_item_id (que no usamos en nuestra estructura multiselect).
//
// Se extienden dos casos:
//  1. Combo raíz (product_type='combo', combo_tagged=True): suma posicional de
//     los combo_tagged que le siguen hasta el primero no-combo_tagged.
//  2. (Sub)sección de combo (display_type section/subsection, combo_tagged=True):
//     suma via getSectionRecords filtrada por combo_tagged.
//
// Para combos nativos (sin combo_tagged) se deja pasar a super() que usa la
// lógica original con combo_item_id y getComboRecords.

patch(SaleOrderLineListRenderer.prototype, {
    getFormattedValue(column, record) {
        if (!this.props.aggregatedFields.includes(column.name)) {
            return super.getFormattedValue(column, record);
        }

        const formatter = registry.category('formatters').get(column.fieldType, (val) => val);
        const fmt = (total) => formatter(total, {
            ...formatter.extractOptions?.(column),
            data: record.data,
            field: record.fields[column.name],
        });

        // Caso 1: combo raíz con nuestra estructura (combo_tagged)
        if (this.isCombo(record) && record.data.combo_tagged) {
            const records = this.props.list.records;
            const idx = records.findIndex((r) => r === record);
            let total = 0;
            for (let i = idx + 1; i < records.length; i++) {
                const r = records[i];
                if (!r.data.combo_tagged) break;
                if (this.isCombo(r)) break;
                if (!this.isSection(r)) {
                    total += r.data[column.name] || 0;
                }
            }
            return fmt(total);
        }

        // Caso 2: (sub)sección de combo con nuestra estructura (combo_tagged)
        if (this.isSection(record) && record.data.combo_tagged) {
            const total = getSectionRecords(this.props.list, record)
                .filter((r) => !this.isSection(r))
                .filter((r) => r.data.combo_tagged)
                .reduce((sum, r) => sum + (r.data[column.name] || 0), 0);
            return fmt(total);
        }

        return super.getFormattedValue(column, record);
    },
});
