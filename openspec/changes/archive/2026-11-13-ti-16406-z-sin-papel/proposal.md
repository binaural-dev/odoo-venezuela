# Sin Z duplicada cuando la máquina no confirma la Z (ti 16406)

## Why

Ticket 16406 (referencia #16444, Monfarmacia). Prueba del usuario con la HKA80
(2026-11-13, sesión 88 de `monfarmacia_t16406_real`): la máquina se quedó sin
papel durante la Z, la sesión guardó 148 y en el papel salió la 0149.

- `printReportZ()` usaba `sendCommand` con reenvío: si la máquina no responde
  en 30 s, el driver vuelve a mandar `I0Z` (hasta 3 intentos). Sin papel la
  máquina acepta el `I0Z` y no confirma a tiempo, y cada reenvío puede sacar
  otra Z, que cierra un día fiscal vacío.
- La caja y el Kiosko trataban esa falta de respuesta como "la Z no salió" y
  un reintento del operador sacaba otra Z.
- Code review (2026-11-13): en la caja, si Odoo fallaba después de imprimir
  la Z, el aviso decía "Error al imprimir Reporte Z", y reintentar imprimía
  otra Z.

Decisión del usuario (2026-11-13): no reenviar la Z sin respuesta, distinguir
la Z impresa sin sincronizar en la caja y probar el error al leer S1.

## What Changes

- `l10n_ve_mf_base`: `printReportZ()` manda `I0Z` sin reenvío cuando no hay
  respuesta (`resendOnNoResponse: false`, como los ítems desde
  `l10n-ve-mf-base-lost-ack-no-resend`) y devuelve `noResponse: true`.
  Versión `19.0.1.1.3` → `19.0.1.1.4`.
- `l10n_ve_pos_mf` (caja): sin respuesta a la Z, vuelve a leer S1. Si el
  contador avanzó, la Z salió y se sincroniza con ese número; si no, avisa
  "Reporte Z sin confirmar" (revisar la máquina, no repetir la Z si salió).
  Si Odoo falla después de imprimir la Z, avisa "Reporte Z impreso con
  advertencia" y que no la repita.
- `l10n_ve_pos_mf_self_order` (Kiosko): lo mismo en `printKioskReportZ`; el
  panel avisa "Reporte Z sin confirmar" (cambio del módulo,
  `ti-16406-kiosko-z-sin-papel`).

## Non-goals

- Reenvío de otros comandos (`I0X`, consultas): no cierran el día fiscal.
- Reintentar la Z sola cuando se repone el papel: lo decide el operador.

## Capabilities

### Modified Capabilities

- `l10n_ve_mf_base`: "Reportes fiscales y gaveta".
- `l10n_ve_pos_mf`: "Reporte Z obligatorio con el S1 leído antes de la Z".

## Impact

- **Módulos**: `l10n_ve_mf_base` (`TfhkaDriver.js`, pruebas Hoot, versión),
  `l10n_ve_pos_mf` (`ClosePosPopup.js`, pruebas Hoot).
- **Todos los clientes con máquina fiscal Web Serial**: la Z del backend
  (`l10n_ve_account_mf`) también usa `printReportZ()`; sin respuesta ya no
  reenvía y muestra el error de la máquina.
- **Despliegue**: `-u l10n_ve_mf_base` (solo assets).
