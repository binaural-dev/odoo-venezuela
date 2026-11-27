## Why

Segunda revisión del PR binaural-dev/odoo-venezuela#1572 (tarea
https://www.binauraldev.com/odoo/project/614/tasks/85447), la de SaulOrte del 19/11 sobre
9445f678. Confirmó que los dos bloqueantes anteriores quedaron corregidos y encontró dos caminos
que rompen la promesa del PR ("un documento por verificar nunca se reimprime a ciegas"):

1. **NC/ND: el ACK del `7` no prueba que el documento se cerró.** `abortTransaction()` devuelve
   `true` con solo el ACK del `7`, el `9` o el `199`, sin releer el estado. Para una NC o ND,
   `_documentOutcome` leía S1 con el documento quizá abierto, y "mismo número" concluía
   `printed: false`, lo que habilita reimprimir. El manual de la TFHKA (medios de pago,
   "Importante") dice que, con pagos parciales, el `7` no anula el documento: sigue en la
   totalización.
2. **La resolución del PdV no tenía los chequeos del asistente.**
   `mf_resolve_print_verification` escribía el número que manda el navegador sin mirar el serial
   de la foto, que sea posterior al número de la foto ni que esté libre. Si la máquina emite otro
   documento fuera del PdV (por ejemplo, una factura del backend) entre la foto y la
   verificación, el contador avanza uno y la verificación le daría al pedido el número de ese
   documento.

Además, el PR tenía conflicto con 19.0 (`l10n_ve_pos_mf` 19.0.3.2.1, precio fiscal a 2
decimales).

## What Changes

1. `_documentOutcome`: para NC y ND, después del `7` se relee el estado (con el mismo margen que
   antes del `7`). Si la máquina no quedó en reposo, el resultado es `printed: null` con
   `reason: "document_open"`; si no responde, `no_response`. Solo con la máquina en reposo se
   compara S1. Las facturas no cambian.
2. `pos.order._mf_check_fiscal_number(number, serial, verification)`: los chequeos del asistente
   (serial de la foto, número mayor que el de la foto y libre en esa máquina para ese tipo de
   documento) en un solo método, que usan el asistente y `mf_resolve_print_verification`.
3. `mf_resolve_print_verification`, antes de escribir un número: si el chequeo falla, no lo
   escribe, deja la marca, lo registra en el chatter (motivo, número informado y foto) y responde
   `{"manual_review": True, "reason"}`. "No emitido", un pedido que ya tenía número y un pedido que
   todavía no está en el servidor siguen igual.
4. PdV: con `manual_review`, el pedido vuelve a como estaba (sin número y por verificar), sale de
   la cola y se avisa al cajero. Los demás caminos no cambian: el número se aplica en la orden
   local antes de llamar al servidor, como antes.
5. Merge de 19.0: `l10n_ve_pos_mf` queda en 19.0.3.3.0 (19.0 está en 19.0.3.2.1).
6. Traducciones es_VE.

## Non-goals

- Volver a llenar la cola local desde el servidor (revisión de SaulOrte, punto 3): no se hace;
  queda como limitación conocida (change `ta-85447-limitaciones-conocidas`).
- "Falla sin foto" después de un pago: sigue como riesgo documentado en el diseño de la 85447.
- Chequear el número que llega con la sincronización de una orden que todavía no estaba en el
  servidor: es el camino de toda orden impresa, fuera de este PR.

## Impact

- `l10n_ve_mf_base`: `TfhkaDriver._documentOutcome` y `_statusAfterAbort`; pruebas Hoot.
- `l10n_ve_pos_mf`: `pos_order.py`, el asistente, `PosStore._mfApplyPrintVerification`, es_VE y
  pruebas Python y Hoot.
- Sin cambios de datos, vistas ni dependencias.
