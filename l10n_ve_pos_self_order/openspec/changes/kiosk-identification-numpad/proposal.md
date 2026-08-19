# Feature: teclado numérico y acciones en la barra inferior en la identificación del Kiosko

## Why

La pantalla de identificación del Kiosko (`l10n_ve_pos_self_order`) pide la
cédula/RIF con un `<input>` de texto, lo que obliga a depender del teclado
físico o del teclado del sistema operativo del terminal. En un Kiosko táctil
sin teclado físico esto deja al cliente sin forma cómoda de introducir la
cédula.

Además, el botón "Continuar" quedaba centrado y a ancho completo debajo del
campo, separado del botón "Atrás" que ya vive en el pie de página. Se pide
unificar las acciones de navegación en la misma barra inferior: "Atrás" a la
izquierda y la acción primaria a la derecha, a la misma altura.

Alcance: pantalla de identificación por cédula del modo **Kiosko**. No toca el
backend, los controladores ni el flujo RPC.

## What Changes

- **Teclado numérico en pantalla** (grid 3×4: dígitos 1-9, retroceso `⌫`, 0 y
  limpiar `C`) debajo del campo de cédula en el paso `identify`. El campo sigue
  siendo editable por teclado físico/OS; el numpad es aditivo.
  - `identification_page.js`: getter `numpadKeys` y handler `onNumpadKey(value)`
    que actualiza `state.vat` (append de dígito / `slice(0,-1)` en retroceso /
    vaciado en limpiar) y resetea `state.error`.
  - `identification_page.xml`: `t-foreach` sobre `numpadKeys` renderizando el
    grid debajo del campo/error.
  - `identification_page.scss`: `.o_ve_numpad` (grid 3×4 centrado, máx. 24rem)
    y `.o_ve_numpad_key` / `.o_ve_numpad_action` (cajas grandes con borde
    reforzado; acento de color para retroceso/limpiar).

- **Acción primaria movida al pie de página**. Se elimina el botón de ancho
  completo del centro. El pie muestra "Atrás" a la izquierda (sin cambios) y la
  acción primaria a la derecha vía el `justify-content-between` ya existente. La
  etiqueta/acción conmuta por paso: "Continue" → `onIdentify()` (paso
  `identify`) y "Create and continue" → `onCreate()` (paso `create`).

## Capabilities

### Modified Capabilities

- `pos-self-order-kiosk-identification`: la pantalla de identificación del
  Kiosko añade un teclado numérico en pantalla para introducir la cédula/RIF y
  reubica la acción primaria en la barra inferior, a la misma altura que
  "Atrás".

## Impact

- **Módulo**: `l10n_ve_pos_self_order` (solo frontend: JS, plantilla OWL, SCSS).
  Bundle `pos_self_order.assets`.
- **No toca** backend, controladores ni el flujo RPC
  (`/l10n_ve_pos_self_order/kiosk/identify` y `.../create`).
- **Cadenas fuente sin cambios** ("Continue", "Create and continue", "Back") —
  las traducciones de `i18n/es_VE.po` siguen aplicando; las teclas del numpad
  son dígitos/símbolos y no requieren traducción.
- **Riesgo**: bajo. Puramente visual y aditivo sobre el paso de identificación.

References: Tarea 78767 (Autopago POS V19),
https://binaural.odoo.com/odoo/action-341/78767
