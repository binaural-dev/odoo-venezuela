# Cerrar sesión e imprimir Z desde el panel de Debug del Kiosko (ti 16406)

## Why

Ticket 16406 (referencia #16444, Monfarmacia): en el Autopago la máquina
fiscal TFHKA está conectada por USB al equipo del Kiosko (Web Serial), así que
solo el navegador del Kiosko puede hablar con ella. La sesión del Kiosko solo
se cierra desde el backend (botón Cerrar de la caja,
`pos.config.action_close_kiosk_session`), que no imprime el Reporte Z ni lo
sincroniza con Odoo: el cierre fiscal del día queda sin hacer o se hace a mano
en la máquina, y las facturas del Kiosko quedan sin su Z en el libro de ventas.

En la caja normal esto ya existe: el botón **Cerrar sesión e imprimir Z** de
`l10n_ve_pos_mf` (`ClosePosPopup.closeSessionAndPrintZ`).

## What Changes

- Panel de Debug del Kiosko (`kiosk_debug_dialog_fiscal.js/.xml`): botón
  **Close session and print Z** (*Cerrar sesión e imprimir Z*) con el mismo
  flujo que la caja:
  1. si la sesión tiene órdenes sin número fiscal, avisa con la lista y no
     sigue;
  2. pide confirmación (la Z es irreversible);
  3. imprime la Z y lee S1 (`printKioskReportZ`, conexión bajo demanda que
     libera el puerto al terminar);
  4. sincroniza la Z con Odoo;
  5. cierra la sesión con el cierre nativo del Kiosko.
  Cualquier fallo corta el flujo en ese paso y lo avisa.
- Servicio `self_order` (`self_order_fiscal.js`): `getKioskCloseSessionPendingOrders`,
  `printKioskReportZ`, `syncKioskReportZ` y `closeKioskSession`.
- Rutas públicas (`controllers/main.py`, validan el `access_token` con
  `_verify_pos_config`):
  - `/l10n_ve_pos_mf_self_order/kiosk/close_session/check`: órdenes de la
    sesión abierta sin `mf_invoice_number` (salvo borradores y canceladas).
  - `/l10n_ve_pos_mf_self_order/kiosk/report_z`: delega en
    `account.move.report_z` y `pos.session.set_report_z`, como la caja. Las
    facturas solo se marcan si la caja ya imprimió con esa máquina.
  - `/l10n_ve_pos_mf_self_order/kiosk/close_session`: vuelve a revisar las
    pendientes y llama a `pos.config.action_close_kiosk_session`; si el cierre
    falla o no termina, responde con error y el framework revierte la petición.
- `tests/test_mf_self_order.py`: el producto se crea con `with_company` (sin
  eso `l10n_ve_stock` rechaza la creación y el `setUpClass` fallaba en
  `origin/19.0`).

## Non-goals

- Cambiar el cierre del Kiosko desde el backend (sigue sin Z).
- Reporte X desde el Kiosko.
- Reintentar solo el cierre cuando la Z ya salió: igual que en la caja, si el
  cierre falla después de la Z, la sesión se cierra desde el backend.

## Capabilities

### New Capabilities

- `pos-mf-self-order-kiosk-close-z`: cierre de la sesión del Kiosko con
  Reporte Z desde el panel de Debug.

## Impact

- **Módulo**: `l10n_ve_pos_mf_self_order` (controlador, servicio, panel de
  Debug, traducción `es_VE` y pruebas). Versión `19.0.1.0.0` → `19.0.1.1.0`.
- **Despliegue**: `-u l10n_ve_pos_mf_self_order` y recargar el Kiosko. Sin
  cambio de esquema ni de datos.
- **Acceso**: el del resto del panel de Debug (`?debug=1` + `access_token` de
  la caja) más la confirmación.
