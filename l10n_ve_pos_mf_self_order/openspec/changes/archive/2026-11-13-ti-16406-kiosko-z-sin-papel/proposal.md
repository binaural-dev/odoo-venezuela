# Kiosko: sin Z duplicada cuando la máquina no confirma la Z (ti 16406)

## Why

Ticket 16406 (referencia #16444, Monfarmacia). Con la HKA80 sin papel durante
la Z, el driver reenvió el `I0Z` y en el papel salió la 0149 mientras la sesión
88 guardó 148. El driver ya no reenvía la Z (`l10n_ve_mf_base`, cambio raíz
`ti-16406-z-sin-papel`) y devuelve `noResponse: true`; el Kiosko tiene que
saber si la Z salió antes de sincronizar o avisar.

## What Changes

- `printKioskReportZ`: si la Z no tiene respuesta, vuelve a leer S1
  (`_readPrintedKioskReportZ`). Con el contador avanzado, la Z salió y devuelve
  ese número para sincronizar; si no, devuelve `unconfirmed: true`.
- Panel de Debug: "Reporte Z sin confirmar" con el aviso de revisar la máquina
  y no repetir la Z si salió.
- Comentario de `POS_MENU_URL` corregido (code review): la caja de 19.0 vuelve
  a `/pos/ui/<caja>`, no al menú de cajas.
- `i18n/es_VE.po`: el título y el aviso nuevos.

## Capabilities

### Modified Capabilities

- `pos-mf-self-order-kiosk-close-z`: "El panel de Debug del Kiosko fiscal cierra
  la sesión con Reporte Z".

## Impact

- **Módulo**: `l10n_ve_pos_mf_self_order` (`self_order_fiscal.js`,
  `kiosk_debug_dialog_fiscal.js`, `i18n/es_VE.po`, pruebas Hoot).
- **Despliegue**: `-u l10n_ve_pos_mf_self_order` y `-u l10n_ve_mf_base`.
