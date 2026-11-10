# Spec delta: revaluation-entry-alternate-zero

## ADDED Requirements

### Requirement: El asiento de ajuste de monedas no realizadas no mueve la moneda alterna

`account.multicurrency.revaluation.wizard._get_move_vals()` SHALL devolver cada
línea del asiento con `not_foreign_recalculate = True`, `foreign_debit = 0` y
`foreign_credit = 0`.

El asiento de ajuste creado por `create_entries()` y su reversión SHALL quedar
con `foreign_debit`, `foreign_credit` y `foreign_balance` en 0 en todas sus
líneas, y `l10n_ve_accountant` SHALL NOT convertir los bolívares del ajuste a la
moneda alterna.

Motivo: el ajuste solo cambia lo que valen en bolívares las partidas en moneda
extranjera; en moneda alterna no hay diferencia. El asistente nativo crea las
líneas con `amount_currency = 0`, por lo que sin la marca el cálculo caía en la
conversión de asientos que no son factura y dejaba importes alternos que no
existen.

#### Scenario: Asiento de ajuste de una cuenta por cobrar

- **GIVEN** una compañía con moneda VEF y alterna USD
- **AND** una factura de 100 USD registrada a 300 Bs/USD, con tasa de cierre 330
- **WHEN** se crea el asiento de ajuste al cierre
- **THEN** la cuenta por cobrar queda con 3.000 Bs de débito y la ganancia con
  3.000 Bs de crédito
- **AND** todas las líneas tienen `foreign_debit`, `foreign_credit` y
  `foreign_balance` en 0

#### Scenario: La reversión también queda en cero

- **GIVEN** el asiento del escenario anterior
- **WHEN** `create_entries()` crea y publica la reversión
- **THEN** todas sus líneas quedan con 0 en la moneda alterna
- **AND** en bolívares asiento y reversión suman 0

#### Scenario: El saldo alterno de la cuenta por cobrar no cambia

- **GIVEN** el asiento de ajuste creado, con la fecha de reversión movida al 15
  de noviembre
- **WHEN** se consulta el saldo de la cuenta por cobrar en la moneda alterna al
  cierre, entre el cierre y la reversión, y después de la reversión
- **THEN** es 100 USD en los tres cortes
- **AND** en bolívares es 33.000, 33.000 y 30.000

#### Scenario: Pago entre el cierre y la reversión

- **GIVEN** el asiento de ajuste con reversión al 15 de noviembre
- **AND** un pago de 100 USD el 5 de noviembre que salda la factura
- **WHEN** se consulta la cuenta por cobrar el 10 de noviembre
- **THEN** el saldo en bolívares es 3.000 y en la moneda alterna es 0

#### Scenario: Un asiento manual en el mismo diario no se ve afectado

- **GIVEN** un asiento manual en el diario de revaluación
- **WHEN** se publica
- **THEN** sus líneas no llevan `not_foreign_recalculate`
- **AND** su valor en moneda alterna se calcula con la tasa de su fecha
