# Spec delta: pos-cross-account-move

## ADDED Requirements

### Requirement: Cruce automático split entrante

El sistema SHALL crear un `account.move` de cruce en `cross_account_journal` cuando un pago split (`split_transactions=True`) de un método de pago con `apply_one_cross_move=True`, `cross_account_journal` y `cross_journal` configurados tiene `amount >= 0`.

El asiento tiene dos líneas: una que debita la cuenta de pago del `cross_journal` (`inbound_payment_method_line_ids.payment_account_id`) y otra que acredita la `outstanding_account_id` del método de pago, ambas por el mismo monto y con `foreign_debit`/`foreign_credit` igual a `payment.foreign_amount`.

#### Scenario: Pago bancario en moneda extranjera al cerrar sesión

- **GIVEN** un método de pago split con `is_foreign_currency=True`,
  `apply_one_cross_move=True` y ambos journals de cruce configurados
- **WHEN** se cierra la sesión de POS con un pago de ese método
- **THEN** aparece un `account.move` nuevo en `cross_account_journal`, en
  estado `draft`, con las cuentas y montos descritos arriba

### Requirement: Cruce automático split saliente (reembolso)

El sistema SHALL crear el asiento espejo cuando el pago split tiene `amount < 0` (vuelto o reembolso): debita la `outstanding_account_id` del método de pago y acredita la cuenta de pago del `cross_journal` (`outbound_payment_method_line_ids.payment_account_id`), usando magnitudes absolutas.

#### Scenario: Reembolso pagado con un método bancario en moneda extranjera

- **GIVEN** un pago split con `amount < 0` y el método configurado para
  cruce
- **WHEN** se cierra la sesión
- **THEN** el `account.move` de cruce invierte las cuentas de débito/crédito
  respecto al caso entrante, con montos en valor absoluto

### Requirement: Cruce automático combine entrante

El sistema SHALL crear el mismo tipo de asiento de cruce para métodos de pago combinados (`split_transactions=False`) con `apply_one_cross_move=True`, dentro de `_create_combine_account_payment`, usando `account.payment.origin_payment_id` para resolver el método de pago (contrato Odoo 19 — el campo `payment_id` fue renombrado).

#### Scenario: Pago combinado en moneda extranjera al cerrar sesión

- **GIVEN** un método de pago combinado con `is_foreign_currency=True` y
  cruce configurado
- **WHEN** se cierra la sesión con pagos de ese método
- **THEN** aparece el `account.move` de cruce correspondiente, con montos
  coherentes con el `foreign_amount` acumulado del método

### Requirement: El asiento de cruce nunca se postea automáticamente

El `account.move` de cruce SHALL crearse siempre en `state="draft"`,
independientemente del estado del resto de la contabilidad de cierre de
sesión.

#### Scenario: Cierre de sesión con cruce pendiente de validación

- **GIVEN** una sesión con al menos un pago que dispara el cruce
- **WHEN** la sesión termina de cerrarse
- **THEN** el `account.move` de cruce queda en `draft`, sin llamar
  `action_post()`

### Requirement: El asiento de cruce toma la secuencia del diario al postearse

El sistema SHALL dejar `account.move.name` sin asignar al crear el asiento de cruce (queda en `/`, el placeholder nativo de borrador), usando `ref` para el texto descriptivo "PoS Payment Method Adjustment". Al postear, Odoo SHALL asignar la secuencia de `cross_account_journal` a `name` mediante su mecanismo nativo (`_compute_name`/`_set_next_sequence`).

#### Scenario: Contabilidad postea el asiento de cruce

- **GIVEN** un asiento de cruce en `draft` con `name` vacío/`/` y `ref` = "PoS Payment Method Adjustment"
- **WHEN** contabilidad lo postea (`action_post()`)
- **THEN** `name` recibe la siguiente secuencia de `cross_account_journal` (no el literal "PoS Payment Method Adjustment"), y `ref` se preserva

### Requirement: Cuenta transitoria con fallback para métodos sin `outstanding_account_id`

El sistema SHALL resolver la pata transitoria del cruce con
`payment_method.outstanding_account_id or
company.account_default_pos_receivable_account_id`, en vez de leer
`outstanding_account_id` directamente. Este SHALL ser el mismo patrón de
fallback que usa el `_get_receivable_account` nativo de Odoo 19.

#### Scenario: Método de pago en efectivo con cruce activado

- **GIVEN** un método de pago `cash` con `is_foreign_currency=True`,
  `apply_one_cross_move=True` y ambos journals de cruce configurados (su
  `outstanding_account_id` está vacío, como en todo método cash — ese campo
  es `invisible="type != 'bank'"` en la vista nativa)
- **WHEN** se cierra la sesión con un pago de ese método
- **THEN** se crea el asiento de cruce usando
  `company.account_default_pos_receivable_account_id` como cuenta
  transitoria, sin lanzar ningún error de base de datos

### Requirement: Sin cruce cuando no aplica

El sistema SHALL NOT crear ningún `account.move` de cruce cuando
`apply_one_cross_move` es `False`, o cuando falta `cross_account_journal` o
`cross_journal` en el método de pago.

#### Scenario: Flag desactivado

- **GIVEN** un método de pago con `apply_one_cross_move=False` (el default)
- **WHEN** se cierra la sesión con pagos de ese método
- **THEN** no se crea ningún `account.move` adicional en ningún diario de
  cruce

#### Scenario: Falta un journal de cruce

- **GIVEN** un método de pago con `apply_one_cross_move=True` pero solo uno
  de `cross_account_journal`/`cross_journal` configurado
- **WHEN** se cierra la sesión
- **THEN** no se crea ningún asiento de cruce y no se lanza ninguna excepción
