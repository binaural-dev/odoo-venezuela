# Tasks

## 1. Frontend (PdV)

- [x] 1.1 `static/src/overrides/models/pos_order_line.js`: helper
      `_isRefundLine()` (`refunded_orderline_id` u `order_id.preset_id.is_return`)
- [x] 1.2 Helper `_quantityAsNumber()` que replica el parseo del core sin
      dejar escapar excepciones del parser sensible al locale
- [x] 1.3 Override de `setQuantity()` que devuelve `{title, body}` cuando la
      cantidad es negativa y la línea no está exenta; delega en `super` en el
      resto de casos
- [x] 1.4 Importar `parseFloat` de `@web/views/fields/parsers` **con alias**
      para no sombrear al `parseFloat` global que ya usa el fichero sobre
      cadenas de `toFixed()`

## 2. Backend

- [x] 2.1 `models/pos_order_line.py`: `@api.constrains("qty",
      "refunded_orderline_id", "order_id")` →
      `_check_qty_not_negative_outside_refund`
- [x] 2.2 Comparación con `float_compare` a la precisión `Product Unit`
- [x] 2.3 Exenciones alineadas con el frontend: `refunded_orderline_id`,
      `order_id.is_refund`, `order_id.preset_id.is_return`
- [x] 2.4 Mensaje en inglés dentro de `_()` con formato
      `_("... %(clave)s", clave=valor)`

## 3. Traducciones

- [x] 3.1 `i18n/es_VE.po`: entrada de la `ValidationError` (odoo-python)
- [x] 3.2 `i18n/es_VE.po`: entradas del título y cuerpo del `AlertDialog`
      (odoo-javascript)
- [x] 3.3 `msgfmt -c` sin errores nuevos

## 4. Verificación manual en navegador (confirmada por el usuario, 2026-07-28)

### 4.A Debe bloquear (líneas de venta normales)

- [x] 4.1 Línea con 2 unidades + tecla `+/-` del numpad → diálogo
      "Cantidad negativa no permitida", la línea sigue en 2, el numpad
      queda limpio (no arrastra el `-2` tecleado)
- [x] 4.2 Línea seleccionada, modo cantidad, teclear `-3` → mismo diálogo,
      cantidad sin cambiar
- [x] 4.3 Combo: seleccionar la línea padre y poner `-1` → diálogo, y
      **ninguna línea hija queda en negativo** (el core propaga la
      cantidad a las hijas dentro de `setQuantity`)

### 4.B Debe permitir

- [x] 4.4 Fijar cantidad `0` en una línea de venta → se aplica sin diálogo
      (es como el cajero borra una línea desde el numpad)
- [x] 4.5 Reembolso completo desde `TicketScreen` → se crea la orden de
      reembolso con líneas negativas, sin ningún diálogo de bloqueo
- [x] 4.6 Ajustar a la baja una línea de reembolso ya creada, de −3 a −2 →
      se aplica normalmente
- [x] 4.7 En una línea de reembolso, intentar cantidad **positiva** → sale
      el mensaje **nativo** "Positive quantity not allowed", no el nuevo
- [x] 4.8 En una línea de reembolso, pedir más de lo reembolsable → sale el
      mensaje **nativo** "Greater than allowed"
- [x] 4.9 Si hay preset con "Return mode" configurado: el carrito sigue
      poniéndose en negativo al seleccionarlo y al agregar productos

### 4.C Servidor

- [x] 4.10 Cobrar y cerrar la orden de reembolso → sincroniza sin
      `ValidationError` (la orden no se queda atascada en el navegador)
- [x] 4.11 Backend, orden de venta del PdV: escribir `qty = -1` en una
      línea → `ValidationError` que nombra el producto y la orden
- [x] 4.12 Backend, orden de reembolso existente: reescribir la `qty` de
      una línea negativa → no falla
- [x] 4.13 `-u l10n_ve_pos` en una BD con órdenes negativas históricas →
      la actualización no falla (`@api.constrains` no revalida datos
      existentes)

### 4.D Regresión (por el import con alias)

- [x] 4.14 **Importes en moneda extranjera por línea siguen correctos**:
      precio unitario, subtotal y total en divisa de cada línea, y que su
      suma cuadre con el total de la orden. El guard vive en el mismo
      fichero que ese cálculo y se tocaron sus imports; si el
      `parseFloat` sensible al locale hubiera sombreado al global, los
      precios en divisa se romperían en es_VE (coma decimal).

## 5. OpenSpec

- [x] 5.1 `proposal.md`, `specs/pos-negative-qty-guard/spec.md`, `tasks.md`
- [x] 5.2 `design.md` (decisiones: cuello de botella en `setQuantity`,
      contrato `{title, body}`, las tres exenciones, doble guard, alias del
      `parseFloat`)
- [x] 5.3 `openspec status --change ...` → 4/4 artefactos
- [x] 5.4 `openspec validate --changes`
