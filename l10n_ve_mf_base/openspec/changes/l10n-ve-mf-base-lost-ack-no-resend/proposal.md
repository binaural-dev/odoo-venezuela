## Why

En Electricos Lebrun (ticket #15814) la máquina fiscal imprimió una factura con
la última línea triplicada y un total distinto al de Odoo. La NC posterior,
armada desde Odoo, solo devolvió las líneas reales y la diferencia quedó viva
en la memoria fiscal. En 2doce pasó varias veces.

`TfhkaDriver.sendCommand` reenvía cualquier comando hasta 3 veces cuando no
recibe respuesta en 5 s. Un ítem no es idempotente: si la MF lo registró y lo
que se perdió fue el ACK, cada reenvío imprime la línea otra vez. El cierre
`1XX` cobra el total que calcula la MF, así que nada lo detecta y Odoo guarda el
número de factura como si todo estuviera bien.

Se reprodujo en la MF de pruebas (serial Z7C7046254) descartando el ACK del
segundo ítem: la línea salió tres veces y la NC posterior salió con dos.

Además, en esa MF (misma familia Z7C que la de Lebrun) se midió que:

- `9` responde NAK siempre, con o sin pagos; solo `7` anula el documento.
  `abortTransaction()` probaba `9` y luego `199`, así que dejaba el documento
  abierto y la venta siguiente pedía reiniciar la impresora.
- S2 y S25 informan la cantidad de artículos siempre en `000000`. La base y la
  cantidad de pagos de S2 sí cambian con cada ítem y cada pago.
- Leer S2 tarda 20–50 ms (picos de 0,5–1,4 s mientras imprime).

## What Changes

- `SerialConnection.read()`: reconoce ACK/NAK por el primer byte recibido,
  aunque llegue en el mismo bloque que otro byte (antes solo si llegaba solo,
  y esperaba un ETX que no venía hasta el timeout).
- `TfhkaDriver.sendCommand()`: opción `resendOnNoResponse` (por defecto
  `true`, comportamiento actual). En `false` devuelve `noResponse: true` en vez
  de reenviar.
- `TfhkaDriver._sendDocumentCommand()`: envía los comandos de factura, NC y ND.
  Para ítems, descuentos `q-` y pagos parciales `2XX`, si no hay respuesta lee
  S2 y decide: si la MF lo registró sigue sin reenviar, si no lo registró lo
  reenvía, y si S2 no cuadra con ninguno de los dos casos falla para que se
  anule el documento. El resto de los comandos mantiene el reintento genérico.
- `TfhkaDriver._verifyRecoveredDocument()`: solo si hubo una recuperación en
  el documento, antes de los pagos compara la base de S2 con la esperada y
  anula si no coinciden. La venta normal no hace lecturas extra.
- `TfhkaDriver.abortTransaction()`: anula con `7` y deja `9` de respaldo.

## Impact

- Módulo: `l10n_ve_mf_base` (`SerialConnection.js`, `TfhkaDriver.js`).
  Consumidores: `l10n_ve_pos_mf` y `l10n_ve_account_mf`, sin cambios.
- Venta normal: mismo tiempo que antes. Con un ACK perdido: una lectura de S2
  y la factura sale correcta, en vez de una factura con líneas de más.
- Fuera de alcance: el reintento a ciegas de los comandos de cierre (`1XX`,
  `199`) y de reportes (`I0Z`), que siguen con el comportamiento anterior.
