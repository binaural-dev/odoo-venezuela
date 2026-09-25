## Context

`l10n_ve_mf_base` es el driver base Web Serial para la máquina fiscal TFHKA en
Odoo 19. Nació de portar el driver de 17.0 (`dff918656`), pero ese port no
incluyó `printRawLines`, porque en 17.0 ese método solo lo usaba
`integra-addons` (voucher de pago Sitef), un consumidor externo que en su
momento no se estaba migrando junto con `odoo-venezuela`. Ahora
`migrate-binaural-pos-sitef-integration-v19` sí necesita el método, y el
código JS de esa migración ya está escrito contra el API de 19.0
(`getFiscalPrinter().printRawLines(data)`), no contra `withConnection()` de
17.0.

## Goals / Non-Goals

**Goals:**
- Exponer `printRawLines(lines)` en `TfhkaDriver.js` (19.0) con la misma
  semántica que en 17.0: enviar cada línea como comando independiente, en
  orden, sin transformarla, verificando estado antes y abortando la
  transacción si algo falla.
- No introducir ningún patrón de conexión ajeno al ya existente en 19.0.

**Non-Goals:**
- No se porta `withConnection()` ni ningún wrapper de conexión por-llamada de
  17.0: la conexión persiste globalmente vía `window.fiscalPrinter` /
  `getFiscalPrinter()` (`l10n_ve_pos_mf/static/src/overrides/PosStore.js`), y
  el consumidor (`integra-addons`) ya está escrito contra ese patrón.
- No se toca `l10n_ve_pos_mf` ni ningún otro módulo: el grep de
  `printRawLines` dentro de `odoo-venezuela` 19.0 no arroja consumidores
  internos, solo la definición añadida aquí.
- No se valida con hardware real en esta fase (requiere navegador + máquina
  fiscal TFHKA conectada por Web Serial).

## Decisions

### 1. Copiar el cuerpo del método tal cual, sin adaptarlo

Las 5 dependencias que usa `printRawLines` (`sendCommand`, `abortTransaction`,
`getStatus`, `_isWaitingState`, `_formatSts`) existen en el `TfhkaDriver.js` de
19.0 con firma idéntica a 17.0:

- `async sendCommand(command, timeout = null, checkStatus = true, skipFlush = false)`
  — idéntica en ambas ramas; `printRawLines` la usa como
  `sendCommand(line, null, false, i > 0)`, patrón ya usado en 19.0 por
  `printInvoice` (fase 1/2 de comandos).
- `async abortTransaction()` — misma firma y semántica (intenta `"9"`, luego
  `"199"`, valida con `getStatus()`).
- `async getStatus()` — misma firma, retorna `{ raw: { sts1, ... }, ... }`
  igual en ambas ramas.
- `_isWaitingState(sts1)` / `_formatSts(sts1)` — funciones puras idénticas
  carácter por carácter en ambos archivos.

Dado esto, el método se portó como copy-paste literal del commit `29b517b4e`,
sin reescribir lógica interna. El resto del archivo divergió bastante entre
17.0 y 19.0 (258 inserciones / 193 eliminaciones en el diff completo), pero no
en las partes de las que depende este método.

### 2. Punto de inserción: entre `abortTransaction()` y `getStatus()`

En 17.0 el orden de métodos es `sendCommand` → `abortTransaction` →
`printRawLines` → `getStatus`. En 19.0 el orden previo a este cambio ya era
`sendCommand` → `abortTransaction` → `getStatus` (mismo orden relativo, sin
`printRawLines` en medio). Se insertó en el mismo hueco para mantener el
archivo de 19.0 alineado con la disposición de 17.0 y no romper la
convención existente ("comandos de bajo nivel" agrupados antes de los
métodos de alto nivel como `printReportX`/`printInvoice`).

### 3. No exponer el método en otra capa

Se revisó (grep) si `printRawLines` debería exponerse también en
`l10n_ve_pos_mf` u otra capa intermedia dentro de `odoo-venezuela`. No se
encontró ningún consumidor interno: el único llamador real está en
`binaural_pos_sitef_integration` (`integra-addons`), que accede al driver a
través de `getFiscalPrinter()` (expuesto por `l10n_ve_pos_mf/static/src/
overrides/PosStore.js`) sin necesitar un método propio en esa capa. No se
agregó código en `l10n_ve_pos_mf`.

## Risks / Trade-offs

- Sin validación con hardware real, un desfase no detectado por `node
  --check` (p.ej. de protocolo/timing) solo aparecería al probar con la
  máquina fiscal física — riesgo aceptado porque el método es portado sin
  modificaciones de una versión que sí corrió en producción en 17.0, y sus
  5 dependencias están confirmadas idénticas.
- El disparador original de este change (`migrate-binaural-pos-sitef-
  integration-v19`, fase 9) queda con este prerequisito resuelto en código,
  pero su validación end-to-end (venta con tarjeta + voucher impreso) sigue
  pendiente de esa fase, con agente Sitef y MF real conectados.
