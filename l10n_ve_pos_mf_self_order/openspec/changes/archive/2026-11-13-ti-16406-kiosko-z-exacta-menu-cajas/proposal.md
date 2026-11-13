# Kiosko: la Z exacta y vuelta al menú de cajas al cerrar (ti 16406)

## Why

Ticket 16406 (referencia #16444, Monfarmacia). Dos ajustes al cierre con Z del
panel de Debug del Kiosko, pedidos por el usuario el 2026-11-13:

- **Una Z de más.** Igual que la caja, `printKioskReportZ` leía S1 después de
  imprimir la Z (el contador ya la cuenta) y el servidor le suma 1. Con la HKA80
  de pruebas la máquina imprimió la Z 0147 y la sesión guardó 148. El flujo IoT
  lee S1 antes de la Z; ahí el +1 es correcto.
- **Al cerrar, el Kiosko se quedaba en la pantalla de pedidos** sin sesión. La
  caja, al cerrar, va al menú de selección de cajas del PdV
  (`PosStore.redirectToBackend` → `/odoo/action-point_of_sale.action_client_pos_menu`).

## What Changes

- `printKioskReportZ` lee S1 antes de `printReportZ()`. Si S1 no responde o no
  trae serial y contador, no imprime la Z (antes la Z salía sin sincronizar y un
  segundo intento imprimía otra). Ya no devuelve `printed`: con
  `success: false` la Z nunca salió.
- El panel avisa "Error al imprimir el Reporte Z" cuando la Z no sale (S1 o
  máquina) y, tras cerrar la sesión, lleva al menú de selección de cajas.
- La ruta `report_z` no cambia (solo su documentación del contador).
- `i18n/es_VE.po`: el aviso nuevo de S1 reemplaza al de "Z impresa sin S1".
- Prueba Python: `_make_invoice` crea su cliente (el CI no tiene datos demo y
  fallaba con `base.res_partner_1`).

## Non-goals

- Rellenar el número de Z con ceros: decisión del usuario (2026-11-13).
- Ir al menú de cajas cuando el cierre falla: el Kiosko se queda en pantalla con
  el aviso, para cerrar desde el backend.

## Capabilities

### Modified Capabilities

- `pos-mf-self-order-kiosk-close-z`: "El panel de Debug del Kiosko fiscal cierra
  la sesión con Reporte Z".

## Impact

- **Módulo**: `l10n_ve_pos_mf_self_order`
  (`static/src/overrides/self_order_fiscal.js`,
  `static/src/app/debug/kiosk_debug_dialog_fiscal.js`, `controllers/main.py`,
  `i18n/es_VE.po`, `static/tests/unit/kiosk_close_session_z.test.js`,
  `tests/test_kiosk_close_session_z.py`). Sin cambio de versión (el PR ya la
  sube).
- **Despliegue**: `-u l10n_ve_pos_mf_self_order` (traducción nueva).
- **Comportamiento visible**: tras "Cerrar sesión e imprimir Z", el equipo del
  Kiosko queda en el menú de cajas del backend (o en el login si no hay usuario
  con sesión iniciada).
