import { patch } from '@web/core/utils/patch';
import { SaleOrderLineListRenderer } from '@sale/js/sale_order_line_field/sale_order_line_field';

// `getInsertLineContext` es el hook que el nativo ya deja para que otros
// módulos marquen las líneas creadas por el kebab "Agregar una línea" de
// una sección/subsección (ver `addRowInSection`, en
// section_and_note_fields_backend.js). Cuando esa sección pertenece a un
// combo, se agrega una marca de contexto que `sale.order.line.create()`
// usa para setear `combo_added_via_subsection_kebab=True` en la nueva
// línea -- la única forma confiable de saber "esto vino del kebab de la
// subsección" en vez de "del botón global al pie de la lista": cuando el
// combo es lo último de la orden, ambos caminos insertan la línea
// exactamente en la misma posición, así que no se puede distinguir
// después por secuencia/posición.
//
// Se usa `combo_tagged` (booleano) y NO el Many2one `combo_root_line_id`:
// este último no siempre llega resuelto a `record.data` cuando apunta a
// otra línea también sin guardar, mientras la orden entera sigue sin
// guardarse (ver combo_section_subtotal.js para el mismo problema).
patch(SaleOrderLineListRenderer.prototype, {
    getInsertLineContext(record, addSubSection) {
        const context = super.getInsertLineContext(record, addSubSection);
        const belongsToCombo = Boolean(record.data.combo_tagged || this.isCombo(record));
        if (belongsToCombo) {
            context.combo_added_via_subsection_kebab = true;
        }
        return context;
    },
});
