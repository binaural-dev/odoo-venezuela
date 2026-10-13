## Why

Ticket https://binaural.odoo.com/odoo/helpdesk.ticket/15684 (referencia #15722, Eléctricos Lebrun):
el PdV deja vender por encima del stock aunque la caja tenga activo "Cantidad en 0"
(`pos.config.amount_to_zero`), y el ticket pide que el stock se valide **antes** de imprimir en
la MF.

En O17 ese check lo aplicaba un `pay()` de `l10n_ve_pos` antes de la pantalla de pago. En la
migración a O19 ese bloque quedó comentado (`overrides/models/pos_order.js`): el campo sigue en
Ajustes pero no hace nada. El otro check, `not_allow_negative_stock_movement` de `l10n_ve_stock`,
no aplica al PdV: el PdV valida su picking con `_action_done()` y se salta
`_pre_action_done_hook`; además saltaría en el servidor, después de la MF.

## What Changes

- `pos.config.check_stock_availability(qty_by_product)` (nuevo): con `amount_to_zero`, devuelve
  los productos almacenables cuya cantidad en la orden supera el stock **a mano** de la ubicación
  origen del tipo de operación de la caja. Se compara contra lo que hay a mano, no contra lo
  libre: lo reservado por otras órdenes confirmadas no bloquea, la orden que sale tiene prioridad.
- `PosStore.pay()` y `PosStore.validateOrderFast()` (pago rápido, que valida sin pasar por
  `pay()`) llaman a un mismo helper `_checkOrderBeforePayment`: el bloqueo de líneas en 0 que ya
  existía y, con `amount_to_zero`, la suma por producto de las líneas positivas (las devoluciones
  no cuentan) consultada al servidor. Si hay faltantes muestra "Stock insuficiente" con
  pedido/a mano por producto y no cobra, así que no se imprime nada en la MF.
- Sin conexión (`ConnectionLostError`) valida de forma aproximada con el `qty_available` cargado
  al abrir la caja (calculado por almacén, puede estar desactualizado). Cualquier otro error del
  servidor se muestra, no se valida en silencio.
- Si el tipo de operación de la caja no tiene ubicación origen no se valida (si no, se
  calcularía contra todas las ubicaciones internas de la compañía).
- No se reusa la ruta `/validate_products_in_warehouse` del mismo módulo (código de O17 que ningún
  JS de O19 llama): valida contra el disponible libre por almacén y contempla kits de otra tienda,
  otra semántica que la acordada para este check (stock a mano, lo apartado no bloquea).

## Impact

- **Módulo tocado:** `l10n_ve_pos` (19.0.1.20.0 → 19.0.1.22.0; la 1.21.0 la usa el PR del ticket 15725: el que se mergee segundo debe subir su versión).
- **Despliegue:** `-u l10n_ve_pos`. Sin cambio de esquema.
- **Fuera de alcance:** `not_allow_negative_stock_movement` (movimientos internos) sigue sin
  aplicar al PdV; el código comentado de O17 en `pos_order.js` no se toca.
