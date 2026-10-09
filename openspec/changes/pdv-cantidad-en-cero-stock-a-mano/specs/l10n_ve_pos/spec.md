## ADDED Requirements

### Requirement: "Cantidad en 0" bloquea el pago sin stock a mano

Con `amount_to_zero` activo en la caja, al pulsar "Pago" (o al validar con el pago rápido) el PdV DEBE (MUST) comparar la cantidad
pedida por producto almacenable (suma de líneas positivas) contra el stock a mano de la ubicación
origen de la caja y, si alguna la supera, mostrar "Stock insuficiente" con el detalle y no pasar
a la pantalla de pago. Lo reservado por otras órdenes no reduce el stock a comparar.

#### Scenario: Stock a mano suficiente aunque esté reservado por otra orden

- **WHEN** hay 8 a mano, otra orden confirmada reservó 7 y la orden del PdV lleva 7
- **THEN** el PdV pasa a la pantalla de pago

#### Scenario: Stock a mano insuficiente

- **WHEN** hay 1 a mano y la orden del PdV lleva 7
- **THEN** se muestra "Stock insuficiente" con "pedido 7, a mano 1" y no se abre la pantalla de pago ni se imprime en la MF

#### Scenario: Check apagado o producto no almacenable

- **WHEN** la caja no tiene `amount_to_zero`, o el producto es servicio/consumible no almacenable
- **THEN** no se valida stock

#### Scenario: Pago rápido

- **WHEN** la caja usa el pago rápido y la orden lleva más de lo que hay a mano
- **THEN** se muestra "Stock insuficiente" y la orden no se valida ni se imprime en la MF
