# Spec delta: pos-payment-foreign-amount

## ADDED Requirements

### Requirement: pos.payment.foreign_amount se calcula para cualquier método de pago

El sistema SHALL calcular `foreign_amount` (equivalente en la moneda
fuerte de la compañía) para TODO pago del PdV cuando su `amount` local
cambia, usando `pos_order.localToForeign(amount)`, sin importar si el
método de pago está marcado `is_foreign_currency`.

Un pago tendido en moneda local (Bs) SHALL llevar su equivalente en
moneda fuerte igual que cualquier otra línea contable (producto,
impuesto) — `is_foreign_currency` describe en qué moneda el cajero tipeó
el monto, no si el pago necesita seguimiento en moneda fuerte.

#### Scenario: Pago en método local

- **GIVEN** un pago cuyo `payment_method_id.is_foreign_currency` es falso
  (ej. "Efectivo Bs")
- **WHEN** se fija su `amount` (vía `setAmount`)
- **THEN** `foreign_amount` queda en `order.localToForeign(amount)`, no en
  `0`

#### Scenario: Pago en método foráneo (comportamiento sin cambios)

- **GIVEN** un pago cuyo `payment_method_id.is_foreign_currency` es
  verdadero
- **WHEN** se fija su `amount` (vía `setAmount`)
- **THEN** `foreign_amount` queda en `order.localToForeign(amount)`,
  igual que antes de este change

#### Scenario: Sin orden o sin helper de conversión

- **GIVEN** un pago cuyo `pos_order_id` es nulo, o cuya orden no expone
  `localToForeign`
- **WHEN** se recalcula el monto foráneo
- **THEN** `foreign_amount` queda en `0` (no se puede calcular; no se
  lanza error)

### Requirement: Los consumidores de foreign_amount no necesitan cambios propios

El sistema SHALL mantener sin modificaciones a todo consumidor backend o
frontend que lea `pos.payment.foreign_amount` para escribir
`foreign_debit`/`foreign_credit` contables o para sumar/mostrar totales,
porque ya hacen asignación directa (no resta ni división que dependa de
que el valor sea `0` para métodos locales).

#### Scenario: Cierre de sesión con pagos mixtos (locales y foráneos)

- **GIVEN** una sesión de PdV cerrada con pagos en un método local y un
  método foráneo
- **WHEN** `pos.session` genera las líneas de recibo del asiento de
  cierre (`_create_cash_statement_lines_and_cash_move_lines`,
  `_create_bank_payment_moves`, `_create_invoice_receivable_lines`, etc.)
- **THEN** todas las líneas, incluidas las del método local, llevan
  `foreign_debit`/`foreign_credit` distinto de `0` (salvo que el monto
  real redondee a cero a la tasa de la sesión)

#### Scenario: Pago local que salda un recargo IGTF

- **GIVEN** un pago en método local (`apply_igtf = True` en su
  `pos.payment.method`) que salda el recargo IGTF generado por otro pago
  de la misma orden
- **WHEN** `l10n_ve_pos_igtf` calcula `amount_without_igtf` como
  `payment.foreign_amount - payment.foreign_igtf_amount`
- **THEN** el resultado es el equivalente foráneo real de la porción sin
  IGTF, no un valor negativo espurio por partir de `foreign_amount = 0`
