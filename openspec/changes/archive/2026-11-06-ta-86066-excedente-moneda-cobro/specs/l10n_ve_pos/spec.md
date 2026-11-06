## MODIFIED Requirements

### Requirement: Cobro tecleado en la moneda de cobro

Al pagar con un método con moneda de cobro, el PdV DEBE (MUST) proponer lo adeudado en esa moneda y tomar lo tecleado en ella, redondeado a esa moneda. Si es justo lo propuesto, la línea DEBE (MUST) valer en la caja exactamente el restante; si es más, lo tecleado por la tasa, con el signo del restante; si es menos, la conversión de lo tecleado. El pago DEBE (MUST) guardar lo cobrado en `tender_amount` con la moneda del método, y su `foreign_amount` se deriva del monto en la caja.

#### Scenario: Pago exacto en euros

- **WHEN** la venta es de 8.500 Bs y el cajero cobra los 8,47 € propuestos
- **THEN** la línea vale 8.500 Bs, no queda restante y se puede validar

#### Scenario: Pago de más en euros

- **WHEN** la venta es de 8.500 Bs y el cajero teclea 10 €
- **THEN** la línea vale los 10 € convertidos y el vuelto sale en Bs

#### Scenario: Excedente sobre lo adeudado redondeado

- **WHEN** la venta es de 18.560 Bs con el € a 1.004,9565776200 Bs (se proponen 18,47 €) y el cajero teclea 25 €
- **THEN** la línea vale 25.123,91 Bs y el vuelto 6.563,91 Bs, no 25.122,37 y 6.562,37 (excedente medido contra 18,47 €)

#### Scenario: Reembolso con excedente

- **WHEN** un reembolso de una venta cobrada a 1.000 Bs/€ debe 8 € y el cajero teclea 10 €
- **THEN** la línea vale -10.000 Bs, a la tasa original

#### Scenario: Pago parcial en euros

- **WHEN** la venta es de 17.000 Bs y el cajero teclea 5 €
- **THEN** la línea vale la conversión de 5 € y el restante sigue en Bs, en USD y en euros

#### Scenario: Línea y recibo en la moneda de cobro

- **WHEN** se agrega una línea del método en EUR
- **THEN** la línea muestra "€ X / Bs Y" y el recibo muestra los euros junto al nombre del método

#### Scenario: Recibo de un pago anterior a un cambio del método

- **WHEN** después de cobrar en EUR se cambia o se quita la moneda de cobro del método y se reimprime el recibo
- **THEN** el recibo muestra la moneda y el monto con que se cobró, guardados en el pago
