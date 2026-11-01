## ADDED Requirements

### Requirement: Monto en moneda alterna del vuelto en los asientos

Cuando una orden del PdV genera una línea de pago de vuelto/cambio (`pos.payment` con `is_change=True`, creada en el servidor por `pos.order._process_payment_lines`), el sistema DEBE (MUST) poblar su `foreign_amount` y su `foreign_rate` con el equivalente en la moneda alterna del monto de la línea, usando la tasa foránea de la orden (`foreign_currency_rate`). El `foreign_amount` DEBE (MUST) conservar el signo del `amount` de la línea (el vuelto es negativo).

En consecuencia, los asientos contables que construyen las columnas de moneda alterna (`foreign_debit` / `foreign_credit`) a partir de `payment.foreign_amount` —los asientos de pago de factura (`pos.payment._create_payment_moves`) y los asientos cruzados de cierre de sesión (`pos.session`)— DEBEN (MUST) reflejar el monto en moneda alterna del vuelto y NO DEBEN (MUST NOT) dejarlo en 0,00. Como red de seguridad, `_create_payment_moves` DEBE (MUST) derivar el alterno de la tasa de la orden si una línea de pago llega con `foreign_amount` ausente pero con `amount` distinto de 0.

La partida doble en la moneda base NO cambia, y el importe en Bs. de todas las líneas se mantiene igual.

#### Scenario: Vuelto en el asiento de pago de una factura

- **WHEN** el cajero cobra un monto superior al total y no indica método de pago para el vuelto, y la orden se factura
- **THEN** el asiento de pago del vuelto registra el monto del cambio en las columnas Débito y Crédito de la moneda alterna (USD), y al conciliar contra la factura el alterno cuadra (pago alterno − vuelto alterno = alterno de la factura)

#### Scenario: Orden sin vuelto

- **WHEN** la orden se paga por el monto exacto (sin cambio)
- **THEN** no se crea línea de vuelto y el alterno de las demás líneas de pago se mantiene sin cambios

#### Scenario: Vuelto en el cierre de sesión de una orden no facturada

- **WHEN** una orden no facturada con vuelto entra en el asiento cruzado del cierre de sesión
- **THEN** el asiento cruzado refleja el monto del vuelto en la moneda alterna y no queda en 0,00
