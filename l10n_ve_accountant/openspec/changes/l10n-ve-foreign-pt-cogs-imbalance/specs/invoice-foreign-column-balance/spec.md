# Spec delta: invoice-foreign-column-balance

## ADDED Requirements

### Requirement: La contrapartida alterna del término de pago se calcula en neto

El sistema SHALL calcular el importe alterno de las líneas `payment_term` de
una factura emitida en la moneda de la compañía o en la moneda alterna a partir
del **neto** del lado contrario de las demás líneas (`Σ foreign_credit −
Σ foreign_debit` para un `payment_term` del lado débito, y simétricamente al
revés), y SHALL NOT usar la suma bruta de un solo lado.

Motivo: un asiento puede contener pares de líneas autobalanceados, que aportan
el mismo importe alterno como débito y como crédito. El caso vivo son las
líneas COGS que `stock_account._post()` agrega a las facturas con valoración de
inventario en tiempo real, creadas antes de `super()._post()` y por tanto
visibles con el asiento todavía en `draft`. Sumar solo un lado las cuenta una
vez sin compensación y descuadra la columna alterna por ese importe.

El comportamiento para facturas en una tercera moneda no cambia: siguen
anclándose en la conversión agregada del total del documento.

#### Scenario: Factura con valoración de inventario en tiempo real

- **GIVEN** una factura de venta en moneda de compañía por `31.243,04 Bs`
- **AND** líneas de producto e impuesto que suman `42,35` al haber en la
  columna alterna
- **AND** tres pares de líneas COGS que aportan `0,21` al debe y `0,21` al
  haber en la columna alterna
- **WHEN** se distribuye el importe alterno de la línea `payment_term`
- **THEN** la línea `payment_term` recibe `42,35` al debe
- **AND** `Σ foreign_debit = Σ foreign_credit = 42,56` en el asiento

#### Scenario: Factura sin líneas autobalanceadas

- **GIVEN** una factura cuyas líneas no-`payment_term` tienen importe alterno
  en un solo lado (`Σ foreign_debit = 0` para una factura de venta)
- **WHEN** se distribuye el importe alterno de la línea `payment_term`
- **THEN** el valor es idéntico al que daba la suma bruta anterior al fix

#### Scenario: Factura de proveedor

- **GIVEN** una factura de compra, cuyo `payment_term` vive del lado crédito
- **WHEN** se distribuye su importe alterno
- **THEN** recibe `Σ foreign_debit − Σ foreign_credit` de las demás líneas

#### Scenario: Varios plazos de pago

- **GIVEN** una factura con tres líneas `payment_term`
- **WHEN** se distribuye el importe alterno
- **THEN** el total repartido entre los tres plazos es el neto de las demás
  líneas
- **AND** el asiento cuadra en la columna alterna

### Requirement: El asiento de una factura cuadra en la columna alterna

El sistema SHALL garantizar que, para toda factura procesada por la
distribución de término de pago, la suma de `foreign_debit` de sus apuntes
iguale la suma de `foreign_credit`.

La propiedad se sostiene por construcción: asignar al `payment_term` el neto
del lado contrario hace que el total de un lado sea `debe + (haber − debe)`,
que es el total del otro.

#### Scenario: Verificación del invariante

- **GIVEN** una factura de cualquier tipo tras publicarse
- **WHEN** se suman `foreign_debit` y `foreign_credit` de todos sus apuntes
- **THEN** ambas sumas son iguales

### Requirement: Los documentos con importes alternos invertidos de origen no empeoran

El sistema SHALL volver a la suma bruta anterior al fix cuando el neto resulte
negativo —señal de que el documento ya tiene importes alternos inconsistentes
con el signo contable de sus apuntes—, y SHALL NOT escribir un importe alterno
negativo.

Motivo: ningún reparto puede reparar un documento cuyos apuntes ya están mal;
lo único que cabe es no degradarlo más. Esos documentos requieren corrección de
datos.

#### Scenario: Nota de crédito con una línea de impuesto invertida

- **GIVEN** una nota de crédito con una línea de impuesto al debe cuyo importe
  alterno está al haber, y `71,28` de descuadre previo
- **WHEN** se distribuye el importe alterno de su línea `payment_term`
- **THEN** el importe asignado no es negativo
- **AND** coincide con el que daba el comportamiento anterior al fix

### Requirement: Los flujos que no producen facturas no se ven afectados

El sistema SHALL NOT alterar el importe alterno de asientos que no sean
facturas (pagos, IGTF, anticipos, retenciones, cierres de sesión del punto de
venta, extractos bancarios, nómina, costes en destino), ni de asientos que ya
estén publicados.

#### Scenario: Asiento de pago con IGTF

- **GIVEN** un asiento de pago generado al cobrar una factura en divisa con
  IGTF
- **WHEN** se sincronizan sus líneas dinámicas
- **THEN** sus importes alternos no cambian respecto al comportamiento anterior
