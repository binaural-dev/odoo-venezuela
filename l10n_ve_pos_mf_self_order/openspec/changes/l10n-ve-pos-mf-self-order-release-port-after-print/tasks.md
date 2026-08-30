# Tasks

## 1. Diagnóstico

- [x] 1.1 Confirmado: `self_order_fiscal.js` conecta la impresora
      (`ensureFiscalPrinterConnected`) antes de imprimir/reimprimir, pero
      nunca llamaba a `disconnect()`. El puerto quedaba abierto desde la
      primera impresión hasta cerrar el navegador.
- [x] 1.2 Comparado con `l10n_ve_pos_mf` (caja): tampoco desconecta
      automáticamente tras imprimir, pero SÍ ofrece un botón manual
      (`FiscalPrinterButton._disconnect`) para que el cajero libere el
      puerto si lo necesita. El Kiosko no tiene ese control (desatendido).
- [x] 1.3 Revisado `TfhkaDriver`/`SerialConnection` de este repo (19.0): NO
      tienen los helpers `withConnection`/`acquireConnection`/
      `releaseConnection` que sí existen en `odoo-venezuela-17.0`
      (ver [[mf-backend-on-demand-connection]]); el fix usa
      `connect()`/`disconnect()` directos, ya existentes en este driver.

## 2. Fix

- [x] 2.1 `printKioskFiscalInvoice`: envolver la impresión + persistencia en
      un `try/finally` que llama a `_releaseFiscalPrinterConnection` sin
      importar el resultado.
- [x] 2.2 `reprintKioskFiscalCopy`: mismo tratamiento (`finally` con
      liberación del puerto).
- [x] 2.3 Nuevo helper `_releaseFiscalPrinterConnection(printer)`: llama a
      `printer.disconnect()` solo si sigue conectado, atrapa errores (no debe
      romper el flujo de impresión si desconectar falla).
- [x] 2.4 Verificado que la auto-conexión de arranque (`SelfOrder.setup`) y
      el pareo manual (`pairFiscalPrinter`, modo debug) NO se tocaron — siguen
      dejando la conexión abierta hasta la primera impresión / a propósito
      para el técnico.

## 3. OpenSpec

- [x] 3.1 Proposal + spec delta + tasks escritos.
- [x] 3.2 `openspec validate l10n-ve-pos-mf-self-order-release-port-after-print --type change --strict` → válido.

## 4. Segunda pasada — la pestaña seguía reteniendo el puerto

El usuario reportó que, tras el fix de la sección 2, el pareo desde otra
pestaña seguía fallando y la impresión también daba error. Causa raíz
adicional: el arranque del Kiosko (`SelfOrder.setup`) y el pareo manual de
debug (`pairFiscalPrinter`) SÍ abrían el puerto y no lo soltaban.

- [x] 4.1 `SerialConnection.isPaired()` / `TfhkaDriver.isPaired()` (nuevo,
      `l10n_ve_mf_base`): consulta `navigator.serial.getPorts()` SIN abrir el
      puerto. Método aditivo, no toca `autoConnect`/`connect`/`disconnect`
      existentes ni afecta a `l10n_ve_pos_mf` (caja).
- [x] 4.2 `SelfOrder.setup()`: reemplazado `ensureFiscalPrinterConnected()`
      (abría el puerto) por `checkFiscalPrinterPairing()` (nuevo, solo
      pareo). El arranque del Kiosko ya no reserva el puerto.
- [x] 4.3 `pairFiscalPrinter()` (modo debug): ahora libera el puerto en un
      `finally` tras verificar, igual que las demás operaciones puntuales.
- [x] 4.4 Nuevo `checkFiscalPrinterConnection()` (conecta → `getStatus` →
      libera) para que el botón "Comprobar estado de conexión" del panel
      Debug pruebe el hardware de verdad, ya que `useFiscalMachine()`
      (lee `isConnected` en memoria) es `false` casi siempre en reposo con
      el modelo bajo demanda.
- [x] 4.5 `mf_debug_dialog.js`/`.xml`: el badge de estado pasa a reflejar el
      resultado de la última prueba explícita (`state.connected`, con un
      tercer estado "Sin comprobar"), en vez de una lectura reactiva continua
      de `isConnected` que ya no es representativa.
- [x] 4.6 `openspec validate ... --strict` de nuevo tras ampliar proposal +
      spec delta → válido.

## 5. Verificación manual (navegador, por el usuario)

- [ ] 5.1 Completar una orden en el Kiosko con la máquina fiscal conectada →
      tras imprimir, comprobar que `window.fiscalPrinter.isConnected` pasa a
      `false` (o que otra pestaña/backoffice puede tomar el puerto).
- [ ] 5.2 Hacer una segunda transacción justo después → debe reconectar sola
      (sin prompt de selección de puerto) e imprimir normalmente.
- [ ] 5.3 Forzar un fallo de impresión (p. ej. desconectar el cable a medias)
      → confirmar que el puerto igual queda liberado y no hace falta
      reiniciar el navegador para reintentar.
- [ ] 5.4 Reimprimir una copia desde el panel de Órdenes fiscales (modo
      debug) → también libera el puerto al terminar.
- [ ] 5.5 **Caso reportado por el usuario**: con el Kiosko recién cargado
      (sin haber hecho ninguna transacción todavía), abrir OTRA pestaña
      (backoffice/Fiscalizador, o el pareo de otra caja) e intentar
      parear/usar la misma máquina fiscal → ya NO debe fallar por puerto
      ocupado.
- [ ] 5.6 Panel Debug del Kiosko: al abrirlo recién, el badge muestra "Sin
      comprobar"; tras pulsar "Comprobar estado de conexión" o "Parear",
      muestra el resultado real (conectada/desconectada).
