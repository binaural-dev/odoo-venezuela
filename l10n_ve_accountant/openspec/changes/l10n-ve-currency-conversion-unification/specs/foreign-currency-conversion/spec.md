# Spec delta: foreign-currency-conversion

## ADDED Requirements

### Requirement: Toda conversión a moneda alterna usa `_convert()`

El sistema SHALL calcular todo monto en moneda alterna con
`currency._convert()`, y SHALL NOT multiplicar ni dividir a mano por
`foreign_rate`, `foreign_inverse_rate` ni `currency_id.rate`.

Motivo: la migración de v17 (base USD) a v19 (base VEF) intercambió el
significado de `foreign_rate` y `foreign_inverse_rate`
(`l10n_ve_rate/models/res_currency_rate.py::compute_rate`). Una multiplicación
manual depende de recordar cuál de los dos aplica y en qué dirección;
`_convert()` recibe origen y destino como argumentos y es inmune a ese cambio.

#### Scenario: Línea de factura en la moneda de la compañía

- **GIVEN** una compañía con moneda VEF y moneda alterna USD
- **AND** una factura en VEF con una línea de 1.000 VEF
- **AND** una tasa vigente de 50 VEF por USD a la fecha de la factura
- **WHEN** se calcula `foreign_price` de la línea
- **THEN** el valor SHALL ser 20,00 USD, obtenido con `_convert()`

#### Scenario: Asiento manual en una tercera moneda

- **GIVEN** un asiento contable con una línea en EUR
- **AND** ninguna línea en la moneda alterna de la compañía
- **WHEN** se calcula el monto alterno de esa línea
- **THEN** el sistema SHALL convertir desde la moneda de la compañía con
  `_convert()` a la fecha contable del asiento

### Requirement: La precisión la determina el campo, no la moneda destino

Al convertir un valor cuyo campo declara una precisión decimal propia, el
sistema SHALL invocar `_convert(..., round=False)` y SHALL aplicar después
`float_round` con la precisión declarada por el campo.

Motivo: `_convert()` redondea por defecto a los decimales de la moneda destino
(USD = 2), mientras que campos como `foreign_price` usan
`digits="Foreign Product Price"`, una `decimal.precision` configurable desde la
interfaz. El sistema SHALL leer esa precisión en tiempo de ejecución con
`decimal.precision.precision_get()` y SHALL NOT asumir un número fijo de
decimales. Sin este tratamiento, un precio unitario pequeño colapsa a cero y
`foreign_subtotal` arrastra el error multiplicado por la cantidad.

#### Scenario: Precio unitario pequeño con cantidad alta

- **GIVEN** una precisión "Foreign Product Price" mayor que los decimales de
  la moneda alterna
- **AND** una línea de 0,0567 VEF con cantidad 10.000
- **AND** una tasa de 50 VEF por USD
- **WHEN** se calcula `foreign_price`
- **THEN** el valor SHALL conservar la precisión configurada (0,001134 USD con
  4 o más decimales) y SHALL NOT colapsar a 0,00
- **AND** `foreign_subtotal` SHALL ser 11,34 USD

#### Scenario: Ida y vuelta entre dos monedas

- **GIVEN** un precio de 300 USD y una tasa cualquiera
- **WHEN** se convierte a VEF y el resultado se convierte de vuelta a USD
  usando la misma fecha
- **THEN** el valor final SHALL ser exactamente 300 USD

### Requirement: Una sola fuente de fecha para la tasa de cada línea

`account.move.line` SHALL resolver la fecha de la tasa mediante
`_get_foreign_rate_date()`, que devuelve `invoice_date` en facturas y notas de
crédito o débito, y `date` en asientos manuales y de pago.

Motivo: en esta localización `invoice_date` es la fecha de la **tasa**; la
fecha visible del documento y la que determina la fecha contable es
`invoice_date_display` (ver `account.move._get_accounting_date_source`). Los
asientos no tienen `invoice_date`, así que usan la fecha contable.

#### Scenario: Factura con fecha de tasa distinta de la contable

- **GIVEN** una factura con `invoice_date` de hace 30 días y `date` de hoy
- **AND** tasas de 25 y 50 VEF por USD respectivamente
- **AND** una línea de 1.000 VEF
- **WHEN** se calcula `foreign_price`
- **THEN** el valor SHALL ser 40,00 USD (tasa de `invoice_date`)

### Requirement: Los subtotales alternos se calculan con `compute_all`

Cuando una línea tiene impuestos, el sistema SHALL obtener su subtotal en
moneda alterna con `tax_ids.compute_all(...)` pasando la moneda alterna, y
SHALL usar `total_excluded` como valor. Aplica a `account.move.line`,
`sale.order.line` y `purchase.order.line`.

Motivo: la multiplicación directa `foreign_price × cantidad` no descuenta el
impuesto cuando va incluido en el precio, y no redondea a la moneda.

#### Scenario: Impuesto incluido en el precio

- **GIVEN** una línea de 116 VEF con IVA 16% marcado como incluido en precio
- **AND** una tasa de 50 VEF por USD
- **WHEN** se calcula `foreign_subtotal`
- **THEN** el valor SHALL ser 2,00 USD (la base) y SHALL NOT ser 2,32

### Requirement: Los totales del documento se leen de `tax_totals`

Los campos de totales —`foreign_untaxed_total`, `foreign_total_billed`,
`amount_untaxed_total_signed` y `amount_total_signed`— SHALL leerse de
`tax_totals` y SHALL NOT recalcularse con una segunda conversión.

En `tax_totals`, las claves con sufijo `_currency` están en la moneda del
documento y las que no lo llevan en la moneda de la compañía; las que llevan
`_foreign_currency` están en la moneda alterna. Es la misma fuente que usa el
core para `amount_total_cc` (`purchase.order._amount_all`).

Esto incluye el caso de una tercera moneda: `base_amount_foreign_currency` se
arma desde el `foreign_price` de cada línea, que ya viene convertido sea cual
sea la moneda del documento.

#### Scenario: Orden en una tercera moneda

- **GIVEN** una compañía VEF con alterna USD
- **AND** una orden en EUR
- **WHEN** se calculan `foreign_untaxed_total` y `foreign_total_billed`
- **THEN** SHALL coincidir con `tax_totals` y con la suma de los
  `foreign_subtotal` de las líneas

### Requirement: La tasa almacenada en el documento no determina los montos

El cálculo de montos alternos SHALL depender de la tabla de tasas a la fecha
correspondiente, y SHALL NOT usar el valor de `foreign_rate` o
`foreign_inverse_rate` guardado en el documento, aun cuando
`manually_set_rate` esté activo.

Los flujos que heredan una tasa (POS, cierre de ejercicio,
`use_invoice_rate_from_sale_order`) SHALL preservar la equivalencia heredando
la **fecha** de la tasa, no su valor.

#### Scenario: Factura con tasa heredada

- **GIVEN** una factura creada desde una orden con tasa heredada
- **WHEN** se calculan sus montos alternos
- **THEN** SHALL usarse la tasa de la tabla a la fecha heredada
- **AND** el resultado SHALL coincidir con el de la orden de origen

### Requirement: La orden de venta conserva la fecha de su tasa

`sale.order` SHALL exponer `foreign_rate_date` con la fecha de la que se tomó
su tasa. El campo SHALL tener valor desde la creación de la orden, SHALL
actualizarse cuando la tasa se recalcule, y SHALL NOT modificarse mientras la
tasa esté congelada.

`sale.order.line` SHALL convertir con esa fecha, y `_prepare_invoice()` SHALL
pasarla como `invoice_date` de la factura cuando
`use_invoice_rate_from_sale_order` esté activo.

Motivo: el core reescribe `date_order` con la fecha de confirmación
(`_prepare_confirmation_values`), así que `date_order` deja de ser la fecha de
la tasa en cuanto la orden se confirma. Además, al crear la orden el ORM
aplica los `default` y no ejecuta `_compute_rate` —porque `foreign_rate` tiene
el suyo—, por lo que el campo necesita un `default` propio.

#### Scenario: Orden confirmada días después con la tasa congelada

- **GIVEN** una compañía con "Update sale order rate using date order"
  desactivado
- **AND** una orden creada con una tasa y su fecha
- **WHEN** la orden se confirma días más tarde y el core mueve `date_order`
- **THEN** `foreign_rate_date` SHALL conservar la fecha original
- **AND** `foreign_price` de las líneas SHALL mantener su valor

#### Scenario: Coherencia entre la cabecera y sus líneas

- **GIVEN** una orden cuya tasa de cabecera es 50 VEF por USD
- **AND** una línea de 1.000 VEF
- **WHEN** se calcula `foreign_price` de la línea
- **THEN** SHALL ser 20,00 USD, es decir `price_unit / foreign_rate`
