# Spec delta: pos-unit-price-currency-rounding

## ADDED Requirements

### Requirement: El PdV redondea el precio unitario a la precisión de la moneda en que se cobra

El sistema SHALL redondear el precio unitario de cada línea del PdV a la
`decimal_places` de la moneda en la que está expresado (la moneda de la orden)
en el momento en que se fija el precio (`PosOrderline.setUnitPrice`), de modo
que el importe cobrado, el IVA, el IGTF, el autocompletado de pagos, el comando
enviado a la máquina fiscal y la factura resultante se deriven todos del mismo
valor redondeado.

El redondeo SHALL usar `order.roundLocalMoney()` cuando la orden esté en la
moneda principal, y `order.roundForeignMoney()` cuando la orden esté en la
moneda foránea (`_is_order_in_foreign_currency()`). El sistema SHALL derivar el
`foreign_price` a partir del `price_unit` **ya redondeado**, no del valor
original de la tarifa.

Esta regla es una excepción deliberada a la convención de que los precios
unitarios conservan la precisión del catálogo (DP "Product Price"); prioriza la
paridad con la máquina fiscal, que sólo acepta el precio de ítem con 2
decimales.

#### Scenario: Unitario con más de 2 decimales pagado en divisa

- **GIVEN** una orden con una línea de 4 unidades cuyo precio unitario con IVA
  es `5068,865205` Bs (nacido de `precio_$ × tasa`) y todos los pagos en un
  método en divisas (código fiscal 20-24)
- **WHEN** el cajero fija el precio de la línea y valida el pago imprimiendo en
  la máquina fiscal
- **THEN** el `price_unit` de la línea queda en `5068,87` (2 decimales)
- **AND** el `amount_total` de la orden es `20.275,48` y el total con IGTF es
  `20.883,74`
- **AND** la base que calcula la máquina fiscal (`5068,87 × 4 = 20.275,48`) y
  su total con IGTF (`20.883,74`) coinciden con los de Odoo, de modo que el
  cierre `199` es aceptado (ACK) y el documento se corta

#### Scenario: La factura hereda el unitario redondeado

- **GIVEN** la orden anterior facturada
- **WHEN** se genera la `account.move` desde la orden del PdV
- **THEN** la línea de factura toma el `price_unit` redondeado (`5068,87`),
  almacenado como `5068,870000` porque la DP "Product Price" se mantiene en 6
- **AND** no aparece en la factura el valor original de 6 decimales
  (`5068,865205`)

#### Scenario: La moneda foránea y el IGTF siguen derivándose del local

- **GIVEN** una orden en moneda principal (Bs) con líneas cuyo unitario se
  redondeó a 2 decimales
- **WHEN** se calculan los importes en moneda foránea ($) y el IGTF
- **THEN** cada importe foráneo es una única conversión `localToForeign()` del
  importe local redondeado, y la suma de los importes foráneos por línea sigue
  igual al total foráneo de la orden
- **AND** el IGTF se calcula como `round(base_local × porcentaje)` sobre la
  base ya redondeada, sin recálculo paralelo en moneda foránea
