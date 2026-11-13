# La caja avisa cuando la Z salió pero Odoo no se actualizó (ti 16406)

## Why

Ticket 16406 (referencia #16444). Code review del 2026-11-13: en la caja, si la
Z ya se imprimió y falla la sincronización con Odoo, el aviso decía "Error al
imprimir Reporte Z". El cajero entendía que la Z no había salido y, al
reintentar, la máquina imprimía otra Z de un día vacío.

## What Changes

- `ClosePosPopup._printFiscalReportZ`: si la Z ya salió y falla Odoo, avisa
  "Reporte Z impreso con advertencia": no repetir la Z, revisar el libro de
  ventas y cerrar la sesión desde el backend.
- Pruebas Hoot de la caja: Odoo falla después de la Z y S1 que lanza un error.

## Non-goals

- La Z de más cuando la máquina se queda sin papel durante la Z (el driver
  reenvía el `I0Z` sin respuesta). Decisión del usuario (2026-11-13): es el
  comportamiento normal de la máquina fiscal; el driver no cambia.

## Capabilities

### Modified Capabilities

- `l10n_ve_pos_mf`: "Reporte Z obligatorio con el S1 leído antes de la Z".

## Impact

- **Módulo**: `l10n_ve_pos_mf` (`static/src/js/ClosePosPopup.js`, pruebas Hoot).
  Solo assets.
