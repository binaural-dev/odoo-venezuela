## MODIFIED Requirements

### Requirement: Débito y crédito alterno por apunte contable

Cada apunte DEBE (MUST) calcular `foreign_debit`/`foreign_credit` (y su `foreign_balance` derivado) según la jerarquía de `_get_foreign_value`, evaluada en este orden: (1) líneas `payment_term`/`tax` usan `foreign_balance`; (2) líneas `line_section`/`line_note` valen 0; (3) el ajuste manual `foreign_debit_adjustment` y (4) el ajuste manual `foreign_credit_adjustment`; (5) líneas cuya moneda es la alterna **y** con `amount_currency` distinto de cero usan `amount_currency`; (6) asientos que no son facturas usan `_get_non_invoice_foreign_value`; (7) líneas `product`/`cogs` usan `foreign_subtotal` con el signo contable del documento; cualquier otro caso devuelve `None` y el apunte no se modifica. Los apuntes del diario de diferencia cambiaria de la compañía y los marcados con `not_foreign_recalculate` quedan excluidos del recálculo.

La fecha con la que se busca la tasa en cualquier cálculo de moneda alterna del apunte es `_get_foreign_rate_date` (fuente única): para facturas y notas de crédito/débito es `invoice_date` y para el resto (asientos manuales, pagos) es la fecha contable (`date`). Cuando el asiento es un reverso (tiene `reversed_entry_id`), la fecha de tasa DEBE (MUST) ser la del asiento ORIGINAL revertido, siguiendo la cadena de `reversed_entry_id` de forma recursiva, para que el reverso revierta exactamente el importe alterno registrado en el original aunque la tasa haya cambiado entre ambas fechas.

En asientos que no son facturas, `_get_non_invoice_foreign_value` DEBE (MUST) devolver, en este orden: el negativo de la suma de `amount_currency` de las líneas en moneda alterna cuando esa suma no es cero y existe exactamente una línea en moneda de la compañía; la conversión del balance a la moneda alterna a la fecha de tasa del apunte (`_get_foreign_rate_date`, que en un reverso es la del asiento original) cuando la moneda de la línea no es la alterna; y en el resto de casos el balance multiplicado por `foreign_inverse_rate`.

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

#### Scenario: Línea excluida del recálculo

- **WHEN** una línea tiene `not_foreign_recalculate` activo
- **THEN** sus importes alternos no se modifican al recalcular el asiento

#### Scenario: Reverso del asiento de un pago en fecha con otra tasa

- **WHEN** se revierte el asiento de un pago (`move_type` `entry`, con `reversed_entry_id`) en una fecha cuya tasa difiere de la del pago original
- **THEN** el débito/crédito alterno del reverso se calcula con la tasa de la fecha del pago original y cuadra exactamente contra el asiento del pago, sin recalcular a la tasa del día del reverso
