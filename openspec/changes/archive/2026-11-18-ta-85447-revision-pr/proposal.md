## Why

Revisión del PR binaural-dev/odoo-venezuela#1572 (tarea
https://www.binauraldev.com/odoo/project/614/tasks/85447): la de pastor-binaural del 13/11 y
la revisión con IA del 17/11. Se reprodujeron en una copia de `pos_consultor`:

1. **El criterio "la orden sigue en la pantalla de pago" no se cumplía.** Con un pago en un
   método de divisa sin IGTF, el PdV no imprimía, pero sincronizaba la orden como pendiente.
   Devolver `false` en `finalizeValidation` no alcanza: el core navega al recibo igual.
2. **Un pedido "por verificar" se podía imprimir desde Contabilidad.** La factura (o la NC)
   del pedido queda publicada sin número fiscal y el botón "Imprimir" aparece: si la máquina
   ya la había emitido, sale una segunda.
3. **El asistente aceptaba el número de otro documento.** Sugiere el número siguiente a la
   foto, y a él llegan justo los casos en que la máquina emitió algo más en el medio. Aceptaba
   además un número con letras.
4. **No quedaba rastro de la resolución.** Al quitar la marca se perdía la foto que la
   justificaba, y "no emitido" es lo que habilita reimprimir.
5. **Un error inesperado al imprimir no avisaba al cajero.**
6. **`l10n_ve_pos_mf` no subía de versión:** 19.0 ya está en 19.0.3.2.0 por la tarea 16406.

## What Changes

1. `OrderPaymentValidation.isOrderValid` frena la validación, antes de imprimir, si un pago
   usa un código de divisa sin IGTF y hay máquina conectada. El cajero sigue en la pantalla de
   pago. `get_data_invoice` mantiene el chequeo para "Imprimir pedido pendiente".
2. `check_print_out_invoice` y `check_print_out_refund` (`l10n_ve_account_mf`) rechazan el
   documento de un pedido del PdV por verificar.
3. El asistente exige solo dígitos y rechaza un número que ya tiene otro pedido u otra factura
   de la misma máquina y del mismo tipo de documento. Compara el valor ("00000101" es el 101),
   porque la máquina numera aparte facturas, notas de crédito y notas de débito.
4. Resolver un pedido por verificar, desde el PdV o desde el asistente, deja un mensaje en el
   chatter con el resultado, los datos fiscales y la foto previa. El autor es quien resolvió.
5. `pushToMF` avisa también ante un error inesperado. La venta sigue pendiente, como con
   cualquier falla.
6. Filtro "Impresión fiscal por verificar" en los pedidos del backend.
7. `verifyDocument` manda a revisión manual una verificación dañada (sin foto o sin
   `paymentSent`), en vez de concluir "no impresa".
8. El texto del botón de pedidos por verificar pasa a inglés como texto fuente, con su
   traducción es_VE.
9. Versiones: `l10n_ve_pos_mf` 19.0.3.3.0 y `l10n_ve_account_mf` 19.0.1.3.0.
10. Gancho `PosStore._mfOrderGoesToFiscalPrinter(order)`: el bloqueo y la impresión lo
    consultan. `binaural_operative_pos_mf` (integra-addons) lo sobrescribe para las órdenes
    operativas del modo mixto, que nunca van a la máquina.
11. El asistente exige el serial de la foto y un número mayor que el de la foto.
12. Una NC o ND que sigue abierta después del `7` queda por verificar con
    `reason: "document_open"`, sin comparar S1. El PdV la trata como `no_response` y el
    aviso pide reiniciar la máquina.
13. El chatter dice cuando el pedido conserva un número que ya tenía, también si la
    verificación da "no emitido".
15. `verifyDocument` también valida `closeAcked` y `docType`.
14. `MockSerialConnection` gana `_saveDeviceInfo`: la prueba "Conexión exitosa y lectura de
    status" fallaba desde e5eb42abc (19.0).

## Non-goals

- Limitar `mf_set/mf_resolve_print_verification` a las sesiones abiertas del usuario: no
  amplía lo que ya permite `write_mf_invoice_data`.
- Caducidad de la cola local, mutex del driver y el aviso del Kiosko con `printed: null`.
- Éxito con el número anterior cuando el `199` se acepta en un pago sin código programado:
  es un problema previo al PR.
- Separar el resultado verificado en otra tarea: corrige los duplicados del driver anterior
  (incidente de 2doce del 12/11).

## Impact

- `l10n_ve_pos_mf`: `OrderPaymentValidation.js`, `PosStore.js`, `PrintPendingOrderButton.xml`,
  `pos_order.py`, `account_move.py`, el asistente, la vista de pedidos, pruebas y es_VE.
- `l10n_ve_account_mf`: `account_move.py` y es_VE nuevo. Sigue sin depender de
  `l10n_ve_pos_mf`: mira si el campo existe.
- `l10n_ve_mf_base`: `verifyDocument`, `_documentOutcome` (NC/ND abierta) y pruebas Hoot
  (S1 de 16 campos, NC y ND con pago, `MockSerialConnection`).
- integra-addons `binaural_operative_pos_mf`: sobrescribe el gancho en un PR aparte. Hay que
  mergearlo **antes** que este PR, o el mismo día. Sin el gancho nadie llama al override. Al
  revés, mientras falte el puente, una orden operativa del modo mixto pagada con un método
  20-24 sin IGTF previo a la restricción queda frenada. Se despliegan juntos donde haya
  `binaural_operative_pos` con máquina fiscal.
