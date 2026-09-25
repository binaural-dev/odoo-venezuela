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

#### Scenario: `rate` de la línea de impuesto en moneda alterna

- **GIVEN** una factura cuya línea de producto ya tiene `foreign_price`
  calculado con `_convert()` (con la precisión completa de la tabla de tasas)
- **WHEN** se arma la base line que alimenta al motor de impuestos para esa
  línea (`_prepare_product_foreign_base_line_for_taxes_computation`)
- **THEN** el `rate` SHALL derivarse de `foreign_price` y `price_unit` de esa
  misma línea, no de `move.foreign_rate`
- **AND** SHALL NOT introducir una diferencia entre el monto reportado
  (`foreign_price`) y el `rate` que el motor de impuestos usa para
  reconciliar, aunque `foreign_rate` (redondeado a la precisión "Tasa", 6
  decimales) difiera del valor exacto de `_convert()`

Motivo: este sitio quedó fuera del inventario original de TA-74966 (no
aparece en la tabla de 8 sitios productivos revisados) porque no es una
multiplicación manual visible en un campo, sino el `rate` que alimenta al
motor de impuestos del core -- pero viola el mismo requirement: usaba
`move.foreign_rate` directo para calcular, no para informar.

#### Scenario: `rate` de las líneas de pronto pago y redondeo en moneda alterna

- **GIVEN** una factura con descuento por pronto pago (`display_type='epd'`) o
  con una línea de redondeo de caja (`display_type='rounding'`)
- **WHEN** se arma la base line foránea de esa línea
  (`_prepare_epd_foreign_base_line_for_taxes_computation` /
  `_prepare_cash_rounding_foreign_base_line_for_taxes_computation`)
- **THEN** el `rate` SHALL derivarse de la conversión ya hecha para el
  `price_unit` de esa misma línea (`amount_currency` convertido /
  `amount_currency` original), no de `move.foreign_rate`

Motivo: mismo requirement y mismo argumento que la línea de producto -- estos
dos sitios seguían con `rate = self.foreign_rate` sin corregir cuando se
cerró el hallazgo de code review sobre el sitio anterior, dejando el
inventario incompleto.

### Requirement: `_sync_tax_lines` resincroniza la línea de impuesto cuando cambia la fecha que representa la tasa

Cuando `invoice_date` (facturas y notas) o `date` (asientos manuales y de
pago) cambian en una factura en estado `draft`, el sistema SHALL
resincronizar `foreign_balance` de sus líneas de impuesto, aunque ningún otro
dato del cálculo en moneda de la compañía (precio, cantidad, `tax_ids`) haya
cambiado.

Motivo: son las mismas fechas que `_get_foreign_rate_date()` usa como fuente
de la tasa para todo lo demás (`foreign_price`, `foreign_subtotal`) -- si
`_round_mode` no las trackea, el resto del documento se recalcula vía
`_convert()` con la fecha nueva pero la línea de impuesto queda con el
`foreign_balance` de la fecha vieja, congelada.

#### Scenario: Cambio de `invoice_date` en una factura de venta en borrador

- **GIVEN** una factura de venta en estado `draft` con su línea de impuesto ya
  sincronizada a una tasa
- **WHEN** se edita `invoice_date` a una fecha con una tasa distinta, sin
  tocar precio, cantidad ni impuestos de ninguna línea
- **THEN** `foreign_balance` de la línea de impuesto SHALL recalcularse con la
  tasa de la nueva fecha

#### Scenario: Cambio de `date` en un asiento manual en borrador

- **GIVEN** un asiento manual (`move_type == 'entry'`) en estado `draft`
- **WHEN** se edita `date` a una fecha con una tasa distinta
- **THEN** `foreign_balance` de su línea de impuesto SHALL recalcularse con la
  tasa de la nueva fecha

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

### Requirement: El redondeo por línea agrupa por producto, no por impuesto

Cuando `company.tax_calculation_rounding_method` sea `round_per_line`, el
sistema SHALL calcular y redondear el impuesto de **cada línea de
producto** individualmente (en la moneda de la compañía y en la del
documento) antes de sumar los montos ya redondeados en la línea de
impuesto consolidada. El sistema SHALL NOT sumar las bases de todas las
líneas que comparten un mismo impuesto y redondear una sola vez sobre esa
suma, aunque Odoo agrupe esas líneas en una sola `tax_line` por impuesto.

Motivo: la máquina fiscal venezolana (Providencia de Máquinas Fiscales del
SENIAT) calcula y redondea el impuesto de cada renglón antes de acumularlo
por alícuota. El motor de impuestos de Odoo 19 agrupa por impuesto y
calcula una sola vez sobre la base total, sin importar el modo
configurado -- `round_per_line` en Odoo controla en qué paso interno se
redondea dentro de ese cálculo ya agrupado, no si se calcula por línea de
factura. Sin este tratamiento, el total de IVA no coincide con el que
exige la ley, y `amount_currency` (columna nativa) queda desalineado de
`foreign_debit`/`foreign_credit` (columna alterna), que sí calcula por
línea de producto vía `_prepare_product_foreign_base_line_for_taxes_computation`.

#### Scenario: Dos líneas con el mismo impuesto, método de la máquina fiscal

- **GIVEN** una compañía VEF con alterna USD, `tax_calculation_rounding_method`
  en `round_per_line`, y una tasa de 803,34 VEF por USD
- **AND** una factura en USD con dos líneas de 11,16 USD cada una, ambas con
  IVA 16%
- **WHEN** se calcula la línea de impuesto consolidada
- **THEN** el impuesto total SHALL ser 2.868,88 VEF (1.434,44 + 1.434,44,
  cada uno redondeado por línea)
- **AND** SHALL NOT ser 2.868,89 VEF (resultado de sumar las bases primero
  y redondear una sola vez)

#### Scenario: `amount_currency` coincide con `foreign_debit`/`foreign_credit`

- **GIVEN** una factura cuya moneda de documento coincide con la moneda
  alterna de la compañía (ambas USD)
- **AND** `tax_calculation_rounding_method` en `round_per_line`
- **WHEN** se compara `amount_currency` de una línea de impuesto contra
  `foreign_debit - foreign_credit` de esa misma línea
- **THEN** ambos valores SHALL coincidir, porque representan el mismo
  monto en la misma moneda calculado por dos vías distintas

#### Scenario: El widget de totales y el PDF coinciden con lo posteado

- **GIVEN** una factura con `tax_calculation_rounding_method` en
  `round_per_line`
- **WHEN** se lee `amount_tax`/`tax_totals` (lo que muestra el formulario y
  el reporte impreso)
- **THEN** el monto SHALL coincidir con la suma de `balance`/`amount_currency`
  de las líneas de impuesto reales ya posteadas, y SHALL NOT recalcularse
  de forma independiente sumando las bases de `base_lines` y redondeando
  una sola vez

Motivo: `_get_tax_totals_summary` arma este resumen desde `base_lines` a
través del motor del core, un cálculo separado del que produce las líneas
de impuesto reales -- sin sincronizar ambos, la factura mostrada al
cliente y el asiento contable pueden discrepar en el mismo caso que este
requirement busca cerrar.

#### Scenario: Líneas de signo mixto bajo el mismo impuesto

- **GIVEN** una factura con dos líneas bajo el mismo impuesto, una positiva
  y una negativa (ej. un ajuste o descuento global)
- **AND** `tax_calculation_rounding_method` en `round_per_line`
- **WHEN** se calcula el impuesto por línea antes de sumar
- **THEN** la contribución de cada línea SHALL sumarse con su propio signo
- **AND** SHALL NOT usar el valor absoluto de la línea negativa como si
  fuera positivo

### Requirement: Un impuesto encadenado (`include_base_amount`) suma su
propio monto a la base del siguiente impuesto en la misma línea

Cuando un impuesto tiene `include_base_amount=True`, el sistema SHALL
sumar el monto de ESE impuesto (ya calculado para esa misma línea de
producto) a la base de los impuestos siguientes de la misma línea, antes
de calcularlos -- tanto en `round_per_line` como en `round_globally`.

El sistema SHALL derivar ese monto exclusivamente de valores ya calculados
en el mismo ciclo (`fresh_balance_by_line_id`, `amount_currency` recién
calculado), y SHALL NOT leerlo de `base_line['tax_details']` del motor de
impuestos del core, aunque esa estructura ya traiga el encadenado resuelto
correctamente.

Motivo: `base_line['tax_details']` se calcula con la tasa interna que
maneja el propio motor de Odoo, la cual puede estar tan desactualizada
como `record.balance` lo está en este mismo ciclo (ver el requirement de
`fresh_balance_by_line_id` para el mismo problema). Se intentó leer desde
ahí durante el desarrollo de este fix y produjo una regresión verificable
en la suite de tests -- confirmando que ese camino no es seguro en este
punto del ciclo, aunque el dato en sí sea "más completo".

#### Scenario: Impuesto A (10%, encadenado) seguido de Impuesto B (5%)

- **GIVEN** una factura con dos líneas de producto, cada una con el
  Impuesto A (10%, `include_base_amount=True`) y el Impuesto B (5%)
- **WHEN** se calcula el Impuesto B en modo `round_per_line`
- **THEN** la base de cada línea para el Impuesto B SHALL incluir el monto
  del Impuesto A ya calculado para esa misma línea
- **AND** el total del Impuesto B SHALL diferir del que resultaría de
  calcularlo sobre la base sin el Impuesto A sumado

### Requirement: El alcance del redondeo por línea se limita a impuestos
tipo `percent` (incluidos los hijos `percent` de un `group`)

El sistema SHALL corregir el redondeo por línea (`round_per_line`)
únicamente para impuestos con `amount_type == 'percent'`, incluidos los
impuestos hijos de tipo `percent` dentro de un impuesto `group` (el motor
de Odoo los expande a cálculos individuales antes de generar las líneas
contables, así que cada hijo ya pasa por el mismo camino que un `percent`
suelto sin necesitar código adicional).

El sistema SHALL NOT extender esta corrección a otros `amount_type`
(`fixed`, `division`, `code`/fórmula), aunque alguno de ellos presente el
mismo tipo de descuadre entre `round_per_line` y `round_globally` que
tenía `percent` antes de este fix.

Motivo: en la localización venezolana no se utiliza ningún tipo de
impuesto fuera de porcentual (`percent`, directo o como hijo de un
`group`) -- es una decisión de negocio/alcance, no una limitación técnica.
Verificado con `tax.compute_all()` como oráculo independiente:

- `fixed` (monto plano por unidad): el modo de redondeo no le afecta en
  absoluto -- no hay base multiplicada por un porcentaje que pueda
  desalinearse entre `round_per_line` y `round_globally`.
- `division` (impuesto expresado como % del total, no de la base): **sí
  tiene el mismo bug que tenía `percent`**, confirmado sin corregir --
  con datos reales, `round_per_line` nativo dio 1.582,58 Bs cuando el
  método de la máquina fiscal exige 1.576,33 Bs (una divergencia de 6,25
  Bs, mayor que el error de céntimos que tenía `percent`). Queda fuera de
  alcance a propósito.

#### Scenario: Impuesto tipo `division` en modo `round_per_line`

- **GIVEN** una factura con impuesto tipo `division` y
  `tax_calculation_rounding_method` en `round_per_line`
- **WHEN** se compara el monto posteado contra el método de la máquina
  fiscal (calculado con `tax.compute_all()` línea por línea)
- **THEN** el sistema SHALL NOT garantizar que coincidan -- es un
  descuadre conocido y sin corregir, aceptado porque este tipo de
  impuesto no se usa en Venezuela

#### Scenario: Impuesto tipo `fixed`

- **GIVEN** una factura con impuesto tipo `fixed` (monto plano por unidad)
- **WHEN** se compara el resultado entre `round_per_line` y
  `round_globally`
- **THEN** el resultado SHALL ser idéntico en ambos modos

### Requirement: `round_per_line` SHALL ser la configuración esperada
para compañías venezolanas (hallazgo de configuración, no implementado)

La normativa de máquinas fiscales de Venezuela exige el método de
redondeo por línea. El sistema SHALL documentar que
`company.tax_calculation_rounding_method` debe estar en `round_per_line`
para que el cálculo de impuestos coincida con ese método -- el default de
Odoo 19 es `round_globally`, y este módulo NO lo fuerza a `round_per_line`
en ningún dato de instalación (`data/res_company_data.xml` no toca este
campo).

Esto es un hallazgo, no un fix: no se implementó ningún dato de
instalación ni migración que fuerce el valor. Queda pendiente decidir si
se fuerza vía dato de instalación o se documenta como paso manual de
configuración post-instalación.
