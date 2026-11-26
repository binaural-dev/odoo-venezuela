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

### Requirement: Monto en moneda del diario de una línea de extracto creada solo en moneda extranjera

Al crear o editar en el formulario una línea de extracto bancario (`account.bank.statement.line`) con `foreign_currency_id` distinta de la moneda del diario, `amount_currency` distinto de 0 y `amount` en 0 o ausente, el sistema DEBE (MUST) calcular `amount` convirtiendo `amount_currency` a la moneda del diario con la tasa de la fecha del extracto. El sistema NO DEBE (MUST NOT) modificar `amount` cuando el usuario lo informa, cuando no hay moneda extranjera, cuando la moneda extranjera es la del diario o cuando `amount_currency` es 0.

#### Scenario: Solo el monto en moneda extranjera

- **WHEN** se crea una línea con USD 10,82 y sin `amount` en un diario sin moneda, con la tasa del día en 886,2 Bs/$
- **THEN** `amount` es 9.588,68 Bs, el asiento cuadra en Bs y en $, y al conciliar un pago de 10,82 USD no se genera diferencial cambiario

#### Scenario: Monto en Bs informado

- **WHEN** se crea una línea con `amount` 10.000 y USD 10,82
- **THEN** `amount` se guarda como 10.000 sin ajustes

#### Scenario: Último campo editado en el formulario

- **WHEN** en el formulario de la línea el usuario escribe `amount_currency` y luego `amount`
- **THEN** `amount_currency` se recalcula a la tasa de la fecha y `amount` conserva exactamente lo escrito; si edita primero `amount` y luego `amount_currency`, `amount` se recalcula

#### Scenario: Sin moneda extranjera en el formulario

- **WHEN** la línea no tiene moneda extranjera
- **THEN** `amount` queda como se escribió

#### Scenario: Cambio de fecha en el formulario

- **WHEN** el usuario cambia la fecha de una línea con moneda extranjera
- **THEN** `amount_currency` se conserva y `amount` se recalcula con la tasa de la nueva fecha
