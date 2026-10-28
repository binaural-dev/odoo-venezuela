# Fix: liberar el puerto serial de la máquina fiscal tras cada impresión del Kiosko

## Why

Reporte: al hacer una transacción en el Kiosko, tras imprimir la factura
fiscal, el puerto Web Serial de la máquina fiscal (TFHKA) queda retenido
**perpetuamente** — ningún otro consumidor (otra caja, el panel Fiscalizador
del backoffice) puede tomarlo hasta reiniciar el navegador.

Causa: `ensureFiscalPrinterConnected()` (`self_order_fiscal.js`) conecta la
impresora antes de `printKioskFiscalInvoice`/`reprintKioskFiscalCopy`, pero
**nunca la desconectaba** al terminar. En la caja normal (`l10n_ve_pos_mf`,
`FiscalPrinterButton`) esto no es un problema porque hay un cajero presente
que puede pulsar "desconectar" si necesita liberar el puerto; el Kiosko es
**desatendido** (sin botón de cara al cliente, ver proposal de
[[pos-self-order-kiosk-fiscal-print]]) y nunca desconectaba por sí solo, así
que el puerto quedaba abierto desde la primera impresión hasta el cierre de
la pestaña/navegador.

Web Serial es exclusivo por puerto: mientras una pestaña lo tiene abierto
(`port.open()`), ninguna otra pestaña ni aplicación puede abrirlo.

**Ampliación tras primera pasada:** el fix inicial solo tocó
`printKioskFiscalInvoice`/`reprintKioskFiscalCopy`. El usuario reportó que el
síntoma seguía: la pestaña del Kiosko seguía "agarrando" el puerto y el pareo
desde otra pestaña seguía fallando. Causa raíz adicional: `SelfOrder.setup()`
llamaba a `ensureFiscalPrinterConnected()` — que SÍ abre el puerto — al
arrancar la app, y lo dejaba así retenido desde el boot hasta la primera
impresión (que podía tardar minutos si el Kiosko estaba recién iniciado o
inactivo). Además, `pairFiscalPrinter()` (pareo manual, modo debug) conectaba
para verificar y tampoco soltaba el puerto después.

## What Changes

- `printKioskFiscalInvoice` y `reprintKioskFiscalCopy` liberan el puerto
  (`TfhkaDriver.disconnect()`) en un `finally`, tanto si la operación tuvo
  éxito como si falló. Nuevo helper `_releaseFiscalPrinterConnection`, que
  espeja `FiscalPrinterButton._disconnect` de `l10n_ve_pos_mf` pero de forma
  automática (sin gesto del usuario).
- **Arranque del Kiosko ya NO abre el puerto**: `SelfOrder.setup()` ahora
  llama a `checkFiscalPrinterPairing()` (nuevo), que solo consulta
  `navigator.serial.getPorts()` — sin `port.open()` — para saber si hay un
  pareo vigente. Se añadió `isPaired()` a `SerialConnection`/`TfhkaDriver`
  (`l10n_ve_mf_base`) para esto; es un método puramente aditivo, no cambia
  el comportamiento existente de `l10n_ve_pos_mf` (caja).
- `pairFiscalPrinter()` (modo debug) ahora también libera el puerto al
  terminar de verificar — la AUTORIZACIÓN del puerto (lo que permite
  reconectar sin prompt) es independiente de mantenerlo abierto, así que
  liberar no deshace el pareo.
- Nuevo `checkFiscalPrinterConnection()`: prueba real bajo demanda
  (conecta → `getStatus()` → libera) para el botón "Comprobar estado de
  conexión" del panel Debug, que antes solo leía el flag `isConnected` en
  memoria — con el modelo bajo demanda ese flag es `false` casi siempre en
  reposo, así que el botón se había vuelto inútil. El badge de estado del
  panel Debug (`mf_debug_dialog.js/.xml`) ahora refleja el resultado de la
  última prueba explícita (pareo o "Comprobar estado"), con un tercer estado
  "Sin comprobar" en vez de asumir "Desconectada" antes de la primera prueba.
- Cada operación (imprimir, reimprimir, parear, comprobar estado) queda así
  "bajo demanda": conecta justo antes, opera, y desconecta justo después —
  igual al patrón ya aplicado en el backend (`l10n_ve_iot_mf`, ver
  [[mf-backend-on-demand-connection]]) para el mismo problema. La única
  conexión que se deja abierta a propósito es la de una impresión/pareo en
  curso, nunca en reposo.

## Impact

- **Módulos**: `l10n_ve_pos_mf_self_order`
  (`static/src/overrides/self_order_fiscal.js`,
  `static/src/app/debug/mf_debug_dialog.{js,xml}`) y `l10n_ve_mf_base`
  (`static/src/core/SerialConnection.js`, `static/src/drivers/TfhkaDriver.js`
  — solo el método aditivo `isPaired()`, sin tocar métodos existentes). No se
  toca `l10n_ve_pos_mf` (caja).
- **Capability afectada**: `pos-self-order-kiosk-fiscal-print` (delta
  añadido, ver `specs/`).
- **Riesgo**: bajo. Cada operación reconecta sola vía `autoConnect()` (puerto
  ya autorizado, sin gesto de usuario), a costa de una reconexión extra por
  operación (latencia despreciable frente al tiempo de impresión fiscal). El
  panel Debug ya no refleja un estado "conectado" continuo — solo el
  resultado de la última prueba — trade-off aceptado porque el estado
  continuo dejó de ser real con el modelo bajo demanda.
- **Fuera de alcance**: no se introduce el modelo
  `withConnection`/`acquireConnection`/`releaseConnection` de
  `odoo-venezuela-17.0` — este repo (19.0) no tiene esas utilidades en
  `TfhkaDriver`, así que el fix usa `connect()`/`disconnect()`/`isPaired()`
  directos.

References: reporte de usuario (ago 2026), sin tarea asociada.
