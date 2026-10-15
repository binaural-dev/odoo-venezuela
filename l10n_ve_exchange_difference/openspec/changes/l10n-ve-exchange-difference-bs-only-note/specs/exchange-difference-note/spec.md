# exchange-difference-note (delta)

## ADDED Requirements

### Requirement: El cruce de la nota de diferencial no consume saldo en moneda extranjera

El sistema SHALL cerrar la línea por cobrar de la ND/NC de diferencial
únicamente en moneda de la compañía: el partial resultante SHALL llevar 0 en
el lado en moneda extranjera de la línea contraparte, aun cuando esa línea
conserve saldo en divisa (liquidación parcial). El saldo en moneda extranjera
de la contraparte SHALL permanecer intacto y su saldo en moneda de la compañía
SHALL disminuir exactamente el importe de la nota. La nota SHALL quedar
conciliada con un único partial.

La condición SHALL activarse solo mediante la clave de contexto propia
`l10n_ve_exchange_closing_note_line_id` y solo si la contraparte conserva saldo
en moneda de la compañía tras el cruce.

#### Scenario: Pérdida con aplicación parcial (Nota de Crédito)

- **GIVEN** una factura de 100 USD y un pago de 40 USD con tasa menor
- **WHEN** se concilian
- **THEN** la NC queda con exactamente un partial con 0 USD en el lado de la
  factura
- **AND** la línea de la factura conserva 60 USD y su Bs baja exactamente el
  importe de la NC

#### Scenario: Ganancia con aplicación parcial (Nota de Débito)

- **GIVEN** una factura de 40 USD y un pago de 100 USD con tasa mayor
- **WHEN** se concilian
- **THEN** la ND queda con exactamente un partial con 0 USD en el lado del pago
- **AND** la línea del pago conserva 60 USD

#### Scenario: Aplicación completa (control)

- **GIVEN** factura y pago por el mismo monto en USD con tasas distintas
- **WHEN** se concilian
- **THEN** hay una nota, su cruce lleva 0 USD y todos los saldos quedan en 0

#### Scenario: Sin activación fuera del cierre de la nota

- **GIVEN** una previsualización (`shadowed_aml_values`), una pareja nota-nota,
  una contraparte en moneda de la compañía, sin saldo en divisa, o con Bs menor
  o igual al de la nota
- **THEN** el comportamiento nativo no se modifica

### Requirement: El widget de pagos de la factura muestra cada nota como una fila de diferencial

El sistema SHALL mostrar, en el widget "Pagado/Revertido" de la factura, UNA
fila `is_exchange=True` por cada nota viva ligada a la factura (posteada y sin
reversión), en moneda de la compañía y con `partial_id` real, tanto para NC
(cierra contra la factura) como para ND (cierra contra el pago). Las filas
`invoice_payments_widget['content']` de las notas SHALL incluir
`is_exchange_note=True` y `exchange_note_name`. Las notas revertidas y las
reversiones NO SHALL listarse. El asiento nativo de diferencial y las filas de
pagos normales SHALL permanecer sin cambios.

#### Scenario: Nota viva

- **WHEN** la factura tiene una nota viva
- **THEN** el widget muestra una fila de diferencial con el número de la nota
  en Bs

#### Scenario: Nota revertida

- **WHEN** se rompe la conciliación y la nota se revierte
- **THEN** el widget no lista la nota
