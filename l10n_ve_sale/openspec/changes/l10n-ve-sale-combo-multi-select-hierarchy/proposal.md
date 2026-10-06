# Combo: selección múltiple, jerarquía de secciones y reparto de precio

Tarea: https://binaural.odoo.com/odoo/action-341/83853 (TA-83853)

## Why

El wizard nativo de combo (`product.combo`/`product.combo.item`) solo deja
elegir **un** producto por opción, y la línea raíz del combo nunca puede
convertirse en `line_section` (lo impide el `CHECK` de Postgres
`display_type IS NULL OR product_id IS NULL`: una línea con `product_id` no
puede ser sección). El cliente necesita elegir **varios** productos por
opción, con jerarquía visual (sección del combo → subsección por opción →
productos), sin perder nada del mecanismo nativo (`combo_item_id`,
`linked_line_id`, prorrateo de precio).

Además, `binaural_clinics_sale` (repo `integra-addons`) ya había resuelto un
problema relacionado pero distinto: repartir el precio del combo entre sus
ítems según un tipo (`principal`/`percentage`/`fixed_price`) en vez del
prorrateo nativo por `product.combo.base_price`. Es una necesidad genérica
de la localización, no algo específico de clínicas — se trae a
`l10n_ve_sale` y se **elimina** de `binaural_clinics_sale` (ver Impact).

Por último, el combo hoy solo existe en la orden de venta: una factura
creada desde esa orden aplana la estructura, y en una factura directa no se
puede configurar un combo. La misma jerarquía debe funcionar en
`account.move`.

## What Changes

### Selección múltiple como extensión de lo nativo

- `sale.order_line._onchange_order_line` se extiende (no se reemplaza) para
  aceptar N elecciones por `combo_id` en vez de exactamente 1, generando un
  `Command.create` por cada una. La línea real del combo sigue intacta,
  nunca se convierte en sección.
- Jerarquía puramente decorativa y propia (no depende del `parent_id`
  nativo, que es posicional puro): campos planos `combo_parent_line_id`,
  `combo_root_line_id` (Many2one, sin `ondelete='cascade'` — ver más abajo
  por qué) y `combo_tagged` (booleano, espejo de pertenencia a un combo).
- Subsección decorativa (`line_subsection`, sin `combo_item_id`) por cada
  opción con más de un candidato elegible, insertada y re-etiquetada en
  cada onchange por `_retag_combo_hierarchy_for_combo_line`.
- `_quarantine_stray_lines_from_combo`: cualquier producto ajeno al combo
  (botón global "Agregar un producto", o el configurador nativo de
  "productos opcionales" que a veces se abre solo tras confirmar el combo)
  que termine posicionalmente intercalado en el árbol se reubica al final
  del árbol completo, con una sección separadora ("Productos Adicionales")
  para que quede visualmente claro que no es parte del combo.
- `_cleanup_orphaned_combo_lines`: autodestrucción de subsecciones vacías y
  de la raíz del combo cuando se queda sin ningún descendiente.
- Cantidad de cada producto escala con la cantidad del combo padre
  (multiplicador guardado en `combo_item_qty_per_combo`), reafirmada en
  cada ronda porque el core iguala la cantidad de todas las líneas de combo
  a la del padre.
- Kebab recortado a solo "Eliminar" para toda fila que pertenezca a un
  combo (root, subsección o ítem); arrastre bloqueado igual.
- El wizard de combo (`ComboConfiguratorDialog`) permite elegir cantidad
  por producto con botones +/-, incluidos los productos "Incluido" (único
  candidato, sin alternativas) que nativamente no tienen ningún control.
- El nombre del producto combo en la línea ya no muestra el sufijo nativo
  `" x <cantidad>"` (es puramente visual, no toca el dato real).

### Bug de persistencia de Many2one entre líneas nuevas del mismo lote

Un Many2one que apunta a OTRA línea creada en el mismo lote (todo el árbol
de un combo nuevo, guardado por primera vez) no se resuelve de forma
confiable: con `ondelete='cascade'` el ORM intentaba hacer `unlink()` en
cascada sobre ids virtuales del cliente que nunca se guardaron
(`psycopg2.errors.InvalidTextRepresentation: invalid input syntax for type
integer: "virtual_N"`); con `ondelete='set null'` ya no truena, pero el
valor se guarda en `NULL` en vez de con el id real del hermano (confirmado
consultando la base directo). Se resuelve con dos medidas:

1. `ondelete='set null'` en vez de `'cascade'` (el borrado en cascada ya lo
   maneja nuestro propio `unlink()`, no hace falta que la BD también lo
   intente).
2. `sale.order.create()`/`write()` reconstruyen `combo_parent_line_id`/
   `combo_root_line_id` **después de guardar**, con los ids ya reales
   (`_fix_combo_hierarchy_links`), en vez de confiar en que sobrevivan
   desde el onchange.

### Reparto de precio por tipo de ítem (portado desde `binaural_clinics_sale`)

- Nuevo campo `item_type` (`principal`/`percentage`/`fixed_price`) +
  `percentage` en `product.combo.item`.
- Override de `_get_combo_item_display_price()`: `fixed_price` conserva su
  `lst_price` propio; `percentage` recibe un % de lo que queda tras los
  fixed_price; `principal` reparte el resto en partes iguales **por
  línea** (no por cantidad -- decisión explícita del cliente, confirmada:
  si un ítem `principal` tiene cantidad > 1, el total del combo no cuadra
  con su `list_price`, y así se quiere dejar).
- `price_unit` de una línea de ítem de combo pasa a ser editable a mano.

### Extensión a `account.move` (factura directa y desde SO)

Comportamiento idéntico al de la orden de venta, con una diferencia
estructural: en factura la raíz del combo **sí** se convierte en
`line_section` (no existe en `account.move.line` la restricción que lo
impide en la SO, porque al configurar el combo la línea pierde su
`product_id`), y el combo ya no se puede reconfigurar desde el documento.

- Campos `combo_parent_line_id`, `combo_root_line_id`, `combo_tagged`,
  `combo_item_qty_per_combo` (+ `product_template_id`/`product_type`
  relacionados y `selected_combo_items` efímero) en `account.move.line`.
- `account.move._onchange_invoice_line_ids_combo`: al elegir un producto
  combo en la factura, el wizard nativo (`ComboConfiguratorDialog`, abierto
  desde `invoice_combo_product_field.js`) escribe `selected_combo_items`; el
  onchange convierte la línea en sección raíz y crea subsecciones
  (`line_subsection`) y productos, con la misma cantidad por combo.
- `sale.order._create_invoices` llama a `account.move._fix_combo_hierarchy_links_invoice`
  después de crear las facturas: reconstruye `combo_parent_line_id`/
  `combo_root_line_id` con ids reales (posicional si hay secciones combo; si
  no, mapeando desde `sale_line_ids`).
- `sale.order.line._prepare_invoice_line` propaga `combo_tagged` y
  `combo_item_qty_per_combo`, y reemplaza el nombre nativo de la raíz
  (`"{producto} x {cantidad}"`) por solo el nombre del producto.
- Kebab propio de sección/subsección (`invoice_combo_section_kebab.xml`),
  subtotal filtrado por `combo_tagged` y arrastre bloqueado también en la
  lista de factura (`invoice_combo_list_renderer.js`).

### Presentación (SO y factura)

- Nombre de la raíz, secciones y subsecciones del combo en MAYÚSCULAS
  (Python al crear + JS al mostrar en la SO).
- Jerarquía visual tipo árbol por sangría CSS (`static/src/css/
  combo_subsection_indent.scss`): subsección nivel 1, producto nivel 2. No
  se usan espacios en el nombre (el HTML los colapsa).
- Fila bloqueada (sin `::` de arrastre) para toda fila del combo, detectada
  por `combo_tagged`, `display_type='line_subsection'`, `combo_item_id` o
  `combo_parent_line_id` (esto último cubre órdenes guardadas con una
  versión previa donde `combo_tagged` no estaba poblado en las subsecciones).
- `foreign_subtotal` entra a `aggregated_fields` de la lista de la SO para
  que el total de la subsección caiga en la columna correcta.

## Impact

- Módulo: `l10n_ve_sale` (modelos `sale_order.py`, `sale_order_line.py`,
  `product_combo_item.py` nuevo; vista `product_combo_views.xml` nueva;
  JS en `static/src/js/combo_*`).
- Dependencia nueva: `sale_management` (para poder ocultar con seguridad
  "Establecer como opcional" del kebab de combo -- ese ítem lo agrega
  `sale_management`, no `sale`; sin la dependencia explícita, el xpath que
  lo oculta rompería la compilación del bundle en instalaciones sin ese
  módulo instalado).
- `binaural_clinics_sale` (repo `integra-addons`): se **elimina** la copia
  de `item_type`/`percentage` (modelo `product_combo_item.py`, vista
  `product_combo_views.xml`), de `_get_combo_item_display_price`
  (`sale_order_line.py`), del override JS que hacía editable `price_unit`
  (`static/src/overrides`) y sus tests/traducciones. Los campos son los mismos
  (`product.combo.item.item_type`/`percentage`), así que las columnas de la BD
  se conservan: pasan a ser propiedad de `l10n_ve_sale` (que clinics ya
  declara en `depends`). Los tests se portaron a
  `l10n_ve_sale/tests/test_product_combo_item.py` y `test_combo_item_pricing.py`.
- Traducciones `i18n/es_VE.po`: campos `combo_*`, `item_type`/`percentage`
  (traducciones traídas desde clinics: "Tipo de opción", "Porcentaje",
  "Precio fijo"…), campos de `account.move.line` y textos del kebab de factura.
- `migrations/19.0.1.0.10/pre-migrate.py`: crea las columnas combo de
  `account_move_line` (`ALTER TABLE ... IF NOT EXISTS`) para no recalcularlas
  en bases grandes.
- Sin migración de datos para `sale.order.line`: campos nuevos, ningún campo
  existente cambia de significado.
- Bump de manifest `19.0.1.0.8` → `19.0.1.0.10`; nuevo asset SCSS en
  `web.assets_backend`.
