# Feature: botón "Reembolso total" en la pantalla de reembolso del PoS (l10n_ve_pos)

## Why

En el `TicketScreen` del PdV (pantalla donde se selecciona una orden
sincronizada para reembolsar), el flujo nativo de Odoo 19 obliga a
seleccionar línea por línea y teclear la cantidad en el numpad para marcar
qué se va a reembolsar. Para un reembolso completo de todas las líneas de
la orden (el caso más común), esto es lento.

Ya existió un intento de este botón (`FullRefundButton`,
`static/src/app/components/full_refund/`) en la versión previa del módulo
(Odoo 17), pero se eliminó en el commit `f9bb592d9`
("[FIX] l10n_ve_pos: repara flujo de reembolso en PoS", 2026-07-07) porque
dependía de hooks removidos en la migración a Odoo 19
(`_getToRefundDetail`, `_prepareRefundOrderlineOptions`) y de
`order.orderlines` (renombrado a `order.lines`). El propio
`ticket_screen.js` quedó con un comentario-TODO indicando exactamente
contra qué API reescribirlo si se quería reactivar
(`order.lines`, `getToRefundDetail`, `pos.linesToRefund`).

## What Changes

- `static/src/overrides/screens/ticket_screen/ticket_screen.js`: se agrega
  un `patch(TicketScreen.prototype, { onFullRefund() {...} })` que, para la
  orden actualmente seleccionada (`getSelectedOrder()`), recorre todas sus
  líneas (`order.getOrderlines()`) y para cada una obtiene/crea su
  `toRefundDetail` vía el método público `getToRefundDetail(orderline)` (ya
  expuesto por el core en Odoo 19) y fija `toRefundDetail.qty` a la
  cantidad reembolsable (`orderline.qty - orderline.refundedQty`). Se
  saltan las líneas ya vinculadas a una orden de reembolso destino
  (`toRefundDetail.destinationOrder`) y las que no tienen cantidad
  reembolsable pendiente (`refundableQty <= 0`). Se resetea el
  `number_buffer` al inicio para evitar que quede un dígito del numpad a
  medio teclear.
- `static/src/overrides/screens/ticket_screen/ticket_screen.xml`: se
  agrega un `<xpath expr="//div[hasclass('control-buttons')]"
  position="inside">` sobre `point_of_sale.TicketScreen` que inserta un
  botón "Reembolso total" (icono `fa-check-square-o`), con las mismas
  clases CSS que usan los botones nativos de esa fila ("Details", "Print
  Receipt", `InvoiceButton`): `control-button btn btn-secondary btn-lg
  lh-lg flex-grow-1 flex-shrink-1`. El botón solo se renderiza cuando esa
  fila existe, es decir, cuando `isOrderSynced` es verdadero (misma
  condición que ya aplica el core a toda la fila).
- El botón **no** dispara el reembolso por sí mismo: solo precarga las
  cantidades a reembolsar (igual que hacía el `FullRefundButton` v17). El
  usuario sigue pulsando el botón nativo "Refund" (`onDoRefund`) para
  crear efectivamente la orden de reembolso — así puede revisar/ajustar
  cantidades individuales antes de confirmar.

## Impact

- **Capability**: `pos-refund-full-button` (nueva).
- **Módulo**: `l10n_ve_pos`, solo frontend
  (`static/src/overrides/screens/ticket_screen/`). No toca modelos Python
  ni requiere `-u` del módulo, solo recarga de assets del PdV (JS/XML).
- **Riesgo de despliegue**: bajo — el botón es aditivo, no cambia el
  comportamiento del flujo de reembolso nativo (`onDoRefund` sigue igual);
  en el peor caso el usuario deshace las cantidades manualmente antes de
  confirmar.
- **Fuera de alcance (hallazgo relacionado, no corregido en este change)**:
  se detectó que
  `static/src/overrides/components/orderline/orderline.js` método
  `get_refund_orderline()` referencia `this.pos.toRefundLines`, que no
  existe en Odoo 19 (la API real es `this.pos.linesToRefund` como array, o
  `order.uiState.lineToRefund` como dict por orden). Esto puede lanzar
  `TypeError` al mostrar la tasa (`get_rate()`) de una línea dentro de una
  orden de reembolso ya creada. No se toca en este change porque es un bug
  preexistente no relacionado con el botón nuevo; queda documentado aquí
  para dar seguimiento aparte.
