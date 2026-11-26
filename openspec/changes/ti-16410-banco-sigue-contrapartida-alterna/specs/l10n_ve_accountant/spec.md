## MODIFIED Requirements

### Requirement: Débito y crédito alterno por apunte contable

Cada apunte DEBE (MUST) calcular `foreign_debit`/`foreign_credit` (y su `foreign_balance` derivado) según la jerarquía de `_get_foreign_value`, evaluada en este orden: (1) líneas `payment_term`/`tax` usan `foreign_balance`; (2) líneas `line_section`/`line_note` valen 0; (3) el ajuste manual `foreign_debit_adjustment` y (4) el ajuste manual `foreign_credit_adjustment`; (5) líneas cuya moneda es la alterna **y** con `amount_currency` distinto de cero usan `amount_currency`; (6) asientos que no son facturas usan `_get_non_invoice_foreign_value`; (7) líneas `product`/`cogs` usan `foreign_subtotal` con el signo contable del documento; cualquier otro caso devuelve `None` y el apunte no se modifica. Los apuntes del diario de diferencia cambiaria de la compañía y los marcados con `not_foreign_recalculate` quedan excluidos del recálculo.

En asientos que no son facturas, `_get_non_invoice_foreign_value` DEBE (MUST) devolver, en este orden: el negativo de la suma de `amount_currency` de las líneas en moneda alterna cuando esa suma no es cero y existe exactamente una línea en moneda de la compañía; la conversión del balance a la moneda alterna a la fecha del apunte cuando la moneda de la línea no es la alterna; y en el resto de casos el balance multiplicado por `foreign_inverse_rate`.

El importe alterno de una línea DEBE (MUST) recalcularse cuando cambian `amount_currency` o `currency_id` de las demás líneas de su asiento, porque `_get_non_invoice_foreign_value` mira las líneas hermanas: al conciliar una línea de extracto en Bs y pasar su contrapartida a moneda alterna, la línea del banco deja de tomar su monto a la tasa del día y sigue a su contrapartida, y el asiento cuadra en la moneda alterna (ticket #16410).

#### Scenario: Ajuste manual

- **WHEN** un usuario establece `foreign_debit_adjustment` en una línea que no es de impuesto ni de término de pago
- **THEN** `foreign_debit` toma el valor absoluto del ajuste y no se recalcula por tasa

#### Scenario: Ajuste manual en una línea de término de pago

- **WHEN** la línea con ajuste manual tiene `display_type` `payment_term` o `tax`
- **THEN** el importe alterno se toma de `foreign_balance` y el ajuste manual no se aplica

#### Scenario: Asiento manual sin factura

- **WHEN** se crea un asiento de diario en moneda de la compañía sin líneas en moneda alterna
- **THEN** el débito/crédito alterno de cada línea es el balance multiplicado por `foreign_inverse_rate`

#### Scenario: Asiento espejo de una línea en moneda alterna

- **WHEN** un asiento no factura tiene líneas en moneda alterna y exactamente una línea en moneda de la compañía
- **THEN** esa línea recibe como importe alterno el negativo de la suma de `amount_currency` de las líneas en moneda alterna

#### Scenario: Contrapartida del extracto movida a moneda alterna

- **WHEN** una línea de extracto en Bs (con la cuenta puente como contrapartida) se concilia y su contrapartida pasa a USD por un monto que no corresponde a la tasa del día
- **THEN** la línea del banco recibe como importe alterno el negativo del `amount_currency` de la contrapartida y el asiento cuadra en la moneda alterna

#### Scenario: Línea excluida del recálculo

- **WHEN** una línea tiene `not_foreign_recalculate` activo
- **THEN** sus importes alternos no se modifican al recalcular el asiento

## ADDED Requirements

### Requirement: Balance y monto en moneda coherentes al editar una línea del widget de conciliación

Al editar una línea del asiento de un extracto bancario desde el widget de conciliación (`edit_reconcile_line` de `account.bank.statement.line`), cuando la moneda de la línea no es la de la compañía y la línea no está conciliada, el sistema DEBE (MUST) mantener `balance` y `amount_currency` coherentes con la tasa de la fecha del extracto, y el último campo editado manda: si el cambio incluye `amount_currency`, el `balance` es `amount_currency` dividido por la tasa de la compañía hacia esa moneda a la fecha del extracto (el balance que se haya enviado se descarta); si el cambio incluye solo `balance` o `currency_id`, el `amount_currency` es el balance multiplicado por esa tasa. La diferencia contra el monto del extracto DEBE (MUST) quedar en la línea de la cuenta puente. El sistema NO DEBE (MUST NOT) alterar los valores cuando la moneda de la línea es la de la compañía, cuando la línea ya está conciliada (su monto parcial sigue la tasa del documento) ni cuando el cambio no toca `balance`, `amount_currency` ni `currency_id`. Conciliar una línea en otra moneda sin editarla (`set_line_bank_statement_line`) no cambia: el core ya valora el apunte a la tasa de la fecha.

#### Scenario: Monto en moneda editado

- **WHEN** se edita una línea de $1.700 con la tasa del día en 886,2 Bs/$ y el extracto es de −1.700.000 Bs
- **THEN** el balance de la línea es 1.506.540 Bs y la cuenta puente recibe los 193.460 Bs restantes

#### Scenario: Balance forzado a mano

- **WHEN** el usuario envía `amount_currency` 1.700 junto con un `balance` de 1.700.000 que no corresponde a la tasa de la fecha
- **THEN** se descarta el balance enviado, queda 1.700 × 886,2 y la diferencia pasa a la cuenta puente

#### Scenario: Solo el balance cambia

- **WHEN** se cambia la moneda a USD y el balance a 1.700.000 sin enviar `amount_currency`
- **THEN** `amount_currency` es 1.700.000 / 886,2, no queda cuenta puente y el asiento cuadra en Bs y en $

#### Scenario: Línea en moneda de la compañía

- **WHEN** se edita una línea en la moneda de la compañía
- **THEN** los valores enviados se guardan sin ajustes
