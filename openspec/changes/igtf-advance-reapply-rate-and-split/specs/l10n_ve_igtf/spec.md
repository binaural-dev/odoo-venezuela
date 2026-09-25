## ADDED Requirements

### Requirement: Reaplicación de anticipo con IGTF cierra sin residuo

Cuando se desconcilia un pago con IGTF sobre una factura y luego se reaplica el anticipo resultante sobre esa misma factura, el sistema DEBE (MUST) reconocer el asiento "CRUCE DE ANTICIPO" como un pago real al decidir la tasa de conciliación (no la tasa de la fecha de la factura), y DEBE (MUST) absorber el IGTF con el sobrante del anticipo en vez de recortarlo de la línea de cuentas por cobrar/pagar, sin importar si hay o no brecha de fecha entre la factura y el pago original.

En consecuencia, la factura DEBE (MUST) cerrar en estado "pagada" con `amount_residual` en cero tras la reaplicación, sin generar un diferencial cambiario ni un residuo que no corresponda a una diferencia real de pago.

Adicionalmente, un pago que liquida el TOTAL de una factura en una moneda distinta a la de la compañía NO DEBE (MUST NOT) generar un asiento de diferencial cambiario cuando la única causa es el redondeo de la moneda de pago a su propia precisión (no una pérdida/ganancia cambiaria real).

#### Scenario: Reaplicar un anticipo con brecha de tasa entre factura y pago

- **WHEN** una factura en VEF se paga en USD con una fecha de pago distinta a la fecha de factura, se desconcilia el pago y se reaplica el mismo anticipo sobre la misma factura
- **THEN** la factura queda "pagada" con `amount_residual` en 0,00, sin el diferencial cambiario ficticio ni el residuo del tamaño del IGTF

#### Scenario: Pago completo sin brecha de fecha

- **WHEN** una factura en VEF se paga en su totalidad en USD, con o sin diferencia de tasa entre la fecha de la factura y la del pago
- **THEN** no se genera ningún asiento de diferencial cambiario espurio, y la factura cierra pagada

#### Scenario: Pago parcial, subpago o sobrepago genuinos

- **WHEN** el monto pagado difiere del residual de la factura por una cantidad que NO es un artefacto de redondeo de centavos (un pago a mitad de camino, un subpago o un sobrepago deliberados)
- **THEN** la factura refleja ese estado real ('partial' o el sobrante como anticipo/vuelto), sin que la comparación de tolerancia lo confunda con redondeo

#### Scenario: Cantidad decimal y precio de alta precisión

- **WHEN** la factura tiene una línea con cantidad decimal y precio unitario con más de 2 decimales
- **THEN** los tres comportamientos anteriores se sostienen igual que con montos "redondos"
