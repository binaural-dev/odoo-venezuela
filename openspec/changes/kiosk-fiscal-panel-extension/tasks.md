# Tasks

## 1. Server

- [x] 1.1 Quitar la ruta `session_orders` de `controllers/main.py` (movida a
      base). Conservar `write_mf_invoice_data`.

## 2. Servicio fiscal (cliente)

- [x] 2.1 `overrides/self_order_fiscal.js`: eliminar `createKioskInvoice` y el
      getter `kioskFiscalOrders` (ahora en base). Conservar print/reprint/pairing.
- [x] 2.2 Corregir string español hardcodeado sin `_t()` en
      `printKioskFiscalInvoice` (`"Error al imprimir en la máquina fiscal"` →
      `_t("Error while printing on the fiscal machine")`).

## 3. Extensión del panel (cliente)

- [x] 3.1 `app/debug/kiosk_orders_dialog_fiscal.js`: patch de `KioskOrdersDialog`
      con `orderStatus` fiscal (3 estados), `selectedPayment` (Megasoft) y
      `onPrint`.
- [x] 3.2 `app/debug/kiosk_orders_dialog_fiscal.xml`: `t-inherit` que inyecta
      badges, línea de estado, detalle de pago verificado y botones
      Imprimir/Reimprimir en las anclas de base. Frase del número fiscal
      reescrita para no partir el nodo de texto (traducible).

## 4. Extensión del debug (cliente)

- [x] 4.1 `app/debug/kiosk_debug_dialog_fiscal.js`: patch de `KioskDebugDialog`
      con `connected`, `_describe` fiscal, `onCheckStatus`, `onPair`.
- [x] 4.2 `app/debug/kiosk_debug_dialog_fiscal.xml`: `t-inherit` que inserta el
      badge de estado y los botones de máquina fiscal antes de "Ver órdenes".

## 5. Limpieza

- [x] 5.1 Borrar `kiosk_fiscal_orders_dialog.{js,xml}` y `mf_debug_dialog.{js,xml}`.
- [x] 5.2 Borrar `overrides/self_order_index_fiscal.js`; dejar en el `.xml` solo
      el overlay de impresión.

## 6. i18n

- [x] 6.1 `i18n/es_VE.po` reescrito (36 msgids) solo con strings fiscales;
      verificado completo (cada `_t`/nodo de texto tiene `msgid`).
- [x] 6.2 `models/ir_http.py` (nuevo, registrado en `models/__init__.py`):
      override de `_get_translation_frontend_modules_name` que añade
      `l10n_ve_pos_mf_self_order`. SIN esto, `/website/translations` (ruta pública
      del Kiosko) nunca carga el `.po` del módulo y sus strings salen en inglés
      aunque el `.po` esté completo — mismo mecanismo que `l10n_ve_pos_self_order`
      y el core. Causa raíz del "no se traduce lo fiscal".

## 7. Verificación

- [x] 7.1 Sintaxis JS/XML/Python/.po OK; anclas base ↔ xpath fiscal cotejadas.
- [ ] 7.2 Prueba en navegador (usuario): con máquina fiscal, panel muestra estado
      fiscal e Imprimir/Reimprimir; debug muestra estado de conexión/Parear.
      **Pendiente: requiere upgrade de módulos.**
