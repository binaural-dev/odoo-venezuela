## Why

`printRawLines(lines)` no existe en `TfhkaDriver.js` de la rama `19.0`, aunque el
consumidor real (`binaural_pos_sitef_integration`, repo `integra-addons`, change
`migrate-binaural-pos-sitef-integration-v19`) ya llama
`fiscalPrinter.printRawLines(data)` siguiendo el patrón de conexión persistente de
19.0 (`getFiscalPrinter()` / `window.fiscalPrinter`). Sin este método, cualquier
voucher de pago con líneas de formato libre (Sitef, y a futuro Megasoft) falla en
tiempo de ejecución con `printRawLines is not a function` justo después de que el
pago ya fue aprobado por el agente externo (Sitef/VPOS) — la transacción queda
aprobada pero el voucher no se imprime.

## What Changes

- Portar `printRawLines(lines)` desde `origin/17.0:l10n_ve_mf_base/static/src/
  drivers/TfhkaDriver.js` (commit `29b517b4e`) al `TfhkaDriver.js` de la rama
  `19.0`, insertado en el mismo sitio relativo que en 17.0: después de
  `abortTransaction()` y antes de `getStatus()`.
- El método NO incorpora `withConnection()` ni el patrón de conexión por-llamada
  de 17.0 — ese wrapper no existe en 19.0 (la conexión Web Serial persiste
  globalmente, gestionada aparte por `l10n_ve_pos_mf/static/src/overrides/
  PosStore.js`). El cuerpo del método es igual al de 17.0 porque sus 5
  dependencias (`sendCommand`, `abortTransaction`, `getStatus`,
  `_isWaitingState`, `_formatSts`) existen en 19.0 con firma y semántica
  idénticas (verificado línea por línea).

## Capabilities

### New Capabilities

- `tfhka-raw-lines`: envío de una secuencia de comandos/líneas crudas al
  protocolo TFHKA, en el orden recibido y sin transformarlas, con verificación
  de estado antes de imprimir y aborto de la transacción si un comando falla.

## Impact

- Módulo: `l10n_ve_mf_base` (`static/src/drivers/TfhkaDriver.js`).
- Consumidor real, fuera de este repo: `binaural_pos_sitef_integration`
  (`integra-addons`), fase 0 de `migrate-binaural-pos-sitef-integration-v19`.
- Dentro de `odoo-venezuela` no se encontró ningún otro consumidor de
  `printRawLines` (`grep -rn "printRawLines" --include="*.js" .` solo devuelve
  la propia definición) — `l10n_ve_pos_mf` no lo usa; no se tocó ese módulo.
- Sintaxis verificada con `node --check`. Validación con máquina fiscal TFHKA
  real por Web Serial queda pendiente (requiere navegador + hardware).
