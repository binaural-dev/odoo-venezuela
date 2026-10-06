# Tasks

## 1. Selección múltiple sobre lo nativo

- [x] 1.1 Override de `_onchange_order_line` que acepta N elecciones por
      `combo_id` (antes exactamente 1), sin reemplazar el mecanismo nativo
      (`combo_item_id`, `linked_line_id`/`linked_virtual_id` intactos)
- [x] 1.2 Campos propios `combo_parent_line_id`, `combo_root_line_id`,
      `combo_tagged`, `combo_item_qty_per_combo`,
      `combo_added_via_subsection_kebab`
- [x] 1.3 Subsección decorativa (`line_subsection`, sin `combo_item_id`)
      por opción con más de un candidato

## 2. Jerarquía y limpieza en cada onchange

- [x] 2.1 `_retag_combo_hierarchy_for_combo_line`: recorrido posicional que
      NO corta el bloque ante un producto ajeno intercalado (antes sí
      cortaba, y eso hacía que subsecciones reales más adelante en la
      lista perdieran su marca)
- [x] 2.2 `_quarantine_stray_lines_from_combo`: detección por posición en
      el array (no por `sequence`, que resultó frágil), reubicación al
      FINAL del árbol completo con sección separadora "Productos
      Adicionales" (reusada entre rondas, no se duplica)
- [x] 2.3 `_cleanup_orphaned_combo_lines`: autodestrucción de subsección
      vacía y de la raíz sin ningún descendiente
- [x] 2.4 Reafirmación de `product_uom_qty` por multiplicador guardado,
      después de `super()` (el core iguala la cantidad de todas las líneas
      de combo a la del padre en cada ronda)

## 3. Persistencia de la jerarquía (Many2one entre líneas del mismo lote)

- [x] 3.1 Diagnóstico: `ondelete='cascade'` hacía tronar el `write()` real
      con `psycopg2.errors.InvalidTextRepresentation` sobre ids virtuales
      del cliente (`"virtual_N"`)
- [x] 3.2 Cambiado a `ondelete='set null'`
- [x] 3.3 Filtro defensivo en `unlink()`: descarta ids no-enteros antes de
      tocar cualquier campo del recordset
- [x] 3.4 Confirmado por consulta directa a la base que, aun sin
      `ondelete='cascade'`, el Many2one entre líneas nuevas del mismo lote
      se guardaba en NULL (no solo fallaba, sino que persistía mal)
- [x] 3.5 `_fix_combo_hierarchy_links`, enganchado a `create()`/`write()`
      de `sale.order`: reconstruye `combo_parent_line_id`/`combo_root_line_id`
      con ids reales, después de guardar

## 4. UI: kebab, drag, wizard

- [x] 4.1 Kebab recortado a solo "Eliminar" para raíz/subsección/ítem de
      combo (dos mecanismos nativos distintos: `moveSectionUp/Down` para
      secciones normales, `moveCombo` específico de la línea raíz del
      combo -- había que cubrir ambos)
- [x] 4.2 Bloqueo de arrastre (`o_row_draggable` + barrera dura en
      `sortDrop`) para toda fila de combo
- [x] 4.3 Wizard: botones +/- de cantidad por producto, incluida la
      sección "Incluido" (único candidato, sin alternativas, que
      nativamente no tiene ningún control de cantidad)
- [x] 4.4 Sufijo nativo `" x <cantidad>"` en el nombre del producto combo
      ocultado (puramente visual)
- [x] 4.5 Subtotal mostrado junto a una (sub)sección de combo: reemplazado
      el cálculo nativo (posicional, por array) para que sume solo líneas
      con `combo_tagged`

## 5. Reparto de precio por tipo de ítem (portado de `binaural_clinics_sale`)

- [x] 5.1 `item_type`/`percentage` en `product.combo.item`
      (`product_combo_item.py`, nuevo)
- [x] 5.2 Override de `_get_combo_item_display_price`: fixed_price →
      percentage → principal (reparto por línea, no por cantidad --
      confirmado con el cliente que así se quiere dejar)
- [x] 5.3 Vista `product_combo_views.xml` (nueva): expone los campos en el
      form de `product.combo`
- [x] 5.4 `price_unit` editable en línea de ítem de combo
- [x] 5.5 Verificado que el reparto no se ve afectado por nada de la
      jerarquía/subsecciones agregada: `_get_combo_item_display_price` solo
      se invoca para líneas con `combo_item_id`, nunca para subsecciones,
      la raíz ni productos ajenos/adoptados por kebab

## 6. Dependencias y manifest

- [x] 6.1 `sale_management` agregado a `depends` (requerido para ocultar
      con seguridad "Establecer como opcional", que ese módulo agrega al
      kebab -- sin la dependencia explícita, el xpath rompería la
      compilación de assets en instalaciones sin `sale_management`)
- [x] 6.2 Bump de manifest `19.0.1.0.8` → `19.0.1.0.10` (+ asset SCSS)
- [x] 6.3 Traducciones `i18n/es_VE.po` regeneradas y completadas (campos combo,
      `item_type`/`percentage` traídos de clinics, campos de `account.move.line`,
      kebab de factura)

## 7. Extensión a `account.move`

- [x] 7.1 Campos `combo_*` en `account.move.line`
      (`account_move_line.py`) + `pre-migrate.py` para las columnas
- [x] 7.2 `_onchange_invoice_line_ids_combo` y helpers `*_invoice`: raíz
      convertida a `line_section`, subsecciones y productos con cantidad por
      combo, retag, limpieza de huérfanos
- [x] 7.3 `_fix_combo_hierarchy_links_invoice`: reconstruye la jerarquía con ids
      reales (posicional si hay secciones combo, si no vía `sale_line_ids`);
      enganchado a `sale.order._create_invoices`
- [x] 7.4 `sale.order.line._prepare_invoice_line`: propaga `combo_tagged`/
      `combo_item_qty_per_combo`, nombre de la raíz sin sufijo `x {qty}`
- [x] 7.5 JS de factura: wizard al elegir combo
      (`invoice_combo_product_field.js`), subtotal por `combo_tagged`, bloqueo
      de arrastre y kebab propio (`invoice_combo_list_renderer.js`,
      `invoice_combo_section_kebab.xml`)
- [x] 7.6 Vista `account_move_views.xml`: campos combo + `selected_combo_items`
      como `column_invisible` en `invoice_line_ids`

## 8. Presentación

- [x] 8.1 Nombres de raíz/sección/subsección del combo en MAYÚSCULAS
      (SO: `combo_hide_qty_in_name.js` + Python; factura: Python)
- [x] 8.2 Sangría tipo árbol vía SCSS (`combo_subsection_indent.scss`) con clases
      `l10n-ve-combo-subsection`/`l10n-ve-combo-item` puestas por `getRowClass`
- [x] 8.3 Detección de filas de combo robusta (`combo_tagged`, `display_type`,
      `combo_item_id`, `combo_parent_line_id`) para bloquear arrastre y ocultar
      el `::`
- [x] 8.4 `foreign_subtotal` en `aggregated_fields` de la lista de la SO

## 9. Limpieza de `binaural_clinics_sale` (repo `integra-addons`)

- [x] 9.1 Eliminados `models/product_combo_item.py`, `models/sale_order_line.py`,
      `views/product_combo_views.xml` y `static/src/overrides/` (+ referencias
      en `__init__.py` y `__manifest__.py`)
- [x] 9.2 Eliminadas las traducciones de `item_type`/`percentage`/selección y
      de la constraint (ahora viven en `l10n_ve_sale/i18n/es_VE.po`)
- [x] 9.3 Tests portados a `l10n_ve_sale/tests/` y eliminados de clinics
      (`test_product_combo_item.py`, `test_sale_order_line_pricing.py`)
- [ ] 9.4 Actualizar (`-u`) `binaural_clinics_sale` en las bases que lo tengan:
      la vista `binaural_clinics_sale_product_combo_view_form` se borra y la
      reemplaza `l10n_ve_sale_product_combo_view_form`

## 10. OpenSpec

- [x] 10.1 `proposal.md` + spec delta
- [ ] 10.2 `openspec validate --changes`
- [ ] 10.3 Prueba manual en Odoo: combo en SO y factura (directa y desde SO),
      jerarquía/`::`/sangría y tests de `l10n_ve_sale`
