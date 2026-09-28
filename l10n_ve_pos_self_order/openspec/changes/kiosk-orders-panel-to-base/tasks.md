# Tasks

## 1. Loader de órdenes (server)

- [x] 1.1 Añadir la ruta pública `/l10n_ve_pos_self_order/kiosk/session_orders`
      en `controllers/orders.py` (movida desde `l10n_ve_pos_mf_self_order`).
      Valida `access_token` (`_verify_pos_config`); devuelve order/line/payment/
      partner con `_load_pos_self_data_read` (datos genéricos, sin pedir campos
      fiscales).

## 2. Servicio de recuperación (cliente)

- [x] 2.1 `overrides/self_order_recovery.js`: patch de `SelfOrder` con el getter
      `kioskSessionOrders` (paid/done/invoiced, con líneas, ordenadas desc) y
      `createKioskInvoice(order)` (RPC a `create_invoice`, ya existente en base).

## 3. Panel de órdenes (cliente)

- [x] 3.1 `app/debug/kiosk_orders_dialog.js`: componente `KioskOrdersDialog`
      (carga por `session_orders` → `connectNewData`, detalle, `onCreateInvoice`).
- [x] 3.2 `orderStatus` base de dos estados: `pending_invoice` /
      `invoiced` (vía `state === "invoiced"`).
- [x] 3.3 `app/debug/kiosk_orders_dialog.xml`: plantilla con anclas
      `o_kiosk_order_badges|status|payment|actions` para la extensión fiscal.

## 4. Shell de debug (cliente)

- [x] 4.1 `app/debug/kiosk_debug_dialog.js`: componente `KioskDebugDialog`
      (Ver órdenes + reintentos de cola `flush/retryFailed` + `_run`/`_describe`).
- [x] 4.2 `app/debug/kiosk_debug_dialog.xml`: plantilla con ancla
      `o_kiosk_debug_view_orders`.
- [x] 4.3 Botón flotante `🛠 Debug Kiosko` (debug only) + método `openKioskDebug`
      en `overrides/self_order_index.{js,xml}`.

## 5. i18n

- [x] 5.1 `i18n/es_VE.po`: FUSIONADO con el original (que ya existía con las
      traducciones de la pantalla de identificación + backend) más las nuevas del
      panel/debug. 62 traducciones. Verificado que cada string del código/plantilla
      tiene `msgid` (solo queda el "x" multiplicador, inocuo). El mecanismo de
      carga en frontend ya estaba (`models/ir_http.py` añade el módulo a
      `_get_translation_frontend_modules_name`).

## 6. Verificación

- [x] 6.1 Sintaxis: JS (`node --check`), XML (`ET.parse`), Python (`ast.parse`),
      `.po` (`msgfmt -c`).
- [x] 6.2 Anclas base ↔ xpath fiscal cotejadas (5/5).
- [ ] 6.3 Prueba en navegador (usuario): abrir el Kiosko en `?debug=1`, botón
      "🛠 Debug Kiosko", Ver órdenes, Crear factura de una pendiente. Con y sin
      máquina fiscal. **Pendiente: requiere upgrade de módulos.**
- [ ] 6.4 Correr los tests del módulo. **Pendiente.**
