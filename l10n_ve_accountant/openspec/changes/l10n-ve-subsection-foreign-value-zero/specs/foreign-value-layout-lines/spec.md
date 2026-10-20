# Spec delta: foreign-value-layout-lines

## ADDED Requirements

### Requirement: El importe en moneda alterna de una línea de maquetado es cero

`_get_foreign_value()` SHALL devolver `0.0` para todo apunte con
`display_type` en `('line_section', 'line_subsection', 'line_note')`, y SHALL
hacerlo **antes** de evaluar cualquier otra rama del método (ajustes
manuales, línea ya en moneda alterna, conversión).

`l10n_ve_accountant` SHALL NOT asignar `foreign_balance`, `foreign_debit` ni
`foreign_credit` distintos de cero a una línea de maquetado.

Motivo: una línea de maquetado es un encabezado o una nota visual, no es
contable y no puede aportar al cuadre de ninguna columna. `line_subsection`
es el `display_type` que Odoo 19 agregó a esta familia; sin él en la tupla,
la subsección caía por las ramas siguientes y podía recibir un importe
alterno, descuadrando el asiento en la moneda alterna. El orden importa: si
la exclusión se evaluara después de las ramas de ajuste manual, una
subsección con `foreign_debit_adjustment` seteado volvería a recibir importe.

#### Scenario: Documento en moneda alterna con una subsección

- **GIVEN** una compañía con moneda alterna configurada
- **AND** una factura con una línea `line_subsection` entre sus líneas de
  producto
- **WHEN** se postea la factura
- **THEN** la subsección queda con `foreign_balance = 0`, `foreign_debit = 0`
  y `foreign_credit = 0`

#### Scenario: El asiento cuadra en la columna alterna

- **GIVEN** el asiento del escenario anterior, ya posteado
- **WHEN** se suman `foreign_debit` y `foreign_credit` de todos sus apuntes
- **THEN** ambas sumas son iguales

#### Scenario: La exclusión precede a los ajustes manuales

- **GIVEN** un apunte con `display_type = 'line_subsection'` que tiene
  `foreign_debit_adjustment` distinto de cero
- **WHEN** se calcula su importe en moneda alterna
- **THEN** el resultado es `0.0`
- **AND** el ajuste manual no se aplica, porque la rama de maquetado se
  evalúa primero

#### Scenario: Las secciones y notas no cambian de comportamiento

- **GIVEN** un documento con líneas `line_section` y `line_note`, sin
  subsecciones
- **WHEN** se calcula el importe alterno de sus apuntes
- **THEN** el resultado es idéntico al de antes del fix

#### Scenario: Las líneas contables no se ven afectadas

- **GIVEN** un documento con líneas `product`, `tax` y `payment_term`
- **WHEN** se calcula su importe alterno
- **THEN** cada una sigue la rama que le corresponde y su valor no cambia
  respecto a antes del fix
