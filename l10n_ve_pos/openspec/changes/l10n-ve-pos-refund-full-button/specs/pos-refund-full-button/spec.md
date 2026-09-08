# Spec delta: pos-refund-full-button

## ADDED Requirements

### Requirement: Botón "Reembolso total" en el TicketScreen del PdV

El sistema SHALL mostrar un botón "Reembolso total" en la fila de
`control-buttons` del `TicketScreen` (junto a "Details" y "Print Receipt"),
visible en las mismas condiciones que esa fila ya se muestra hoy
(`isOrderSynced` verdadero, es decir, una orden sincronizada seleccionada
para reembolso).

#### Scenario: Botón visible con una orden sincronizada seleccionada

- **GIVEN** un cajero en el TicketScreen con una orden sincronizada
  seleccionada
- **WHEN** se renderiza la pantalla
- **THEN** el botón "Reembolso total" aparece junto a "Details" y "Print
  Receipt"

### Requirement: El botón precarga la cantidad reembolsable de cada línea

Al hacer click en "Reembolso total", el sistema SHALL fijar, para cada
línea de la orden seleccionada, `toRefundDetail.qty` igual a la cantidad
reembolsable (`orderline.qty - orderline.refundedQty`), usando el método
público `getToRefundDetail(orderline)` del `TicketScreen`. El sistema
SHALL NOT modificar líneas que ya estén vinculadas a una orden de
reembolso destino (`toRefundDetail.destinationOrder` truthy) ni líneas sin
cantidad reembolsable pendiente (`refundableQty <= 0`). El sistema SHALL
resetear el `number_buffer` al iniciar la acción.

#### Scenario: Click en "Reembolso total" con una orden sin reembolsos previos

- **GIVEN** una orden sincronizada con N líneas, ninguna reembolsada
  previamente
- **WHEN** el cajero hace click en "Reembolso total"
- **THEN** las N líneas quedan con `toRefundDetail.qty` igual a su
  cantidad original, visibles en el ticket como "To Refund: <cantidad>"

#### Scenario: Click en "Reembolso total" con una línea parcialmente reembolsada

- **GIVEN** una orden con una línea que ya tiene `refundedQty > 0` y
  `refundedQty < qty`
- **WHEN** el cajero hace click en "Reembolso total"
- **THEN** esa línea queda con `toRefundDetail.qty` igual solo al
  remanente pendiente (`qty - refundedQty`), no a la cantidad original

#### Scenario: Click en "Reembolso total" con una línea ya vinculada a otra orden de reembolso

- **GIVEN** una línea cuyo `toRefundDetail.destinationOrder` ya apunta a
  una orden de reembolso existente
- **WHEN** el cajero hace click en "Reembolso total"
- **THEN** esa línea no se modifica

### Requirement: El botón no dispara el reembolso por sí mismo

El sistema SHALL limitarse a precargar cantidades; el sistema SHALL NOT
crear la orden de reembolso ni navegar a `PaymentScreen` como efecto de
"Reembolso total". La creación de la orden de reembolso sigue
requiriendo que el cajero pulse el botón nativo "Refund"
(`onDoRefund`).

#### Scenario: Después de "Reembolso total" el cajero puede seguir ajustando cantidades

- **GIVEN** el cajero ya pulsó "Reembolso total"
- **WHEN** selecciona una línea individual y teclea una cantidad distinta
  en el numpad
- **THEN** esa línea se actualiza normalmente (comportamiento nativo de
  `_onUpdateSelectedOrderline` sin cambios), y solo al pulsar "Refund" se
  crea la orden de reembolso con las cantidades finales
