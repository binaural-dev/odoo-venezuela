# Spec delta: pos-cross-account-move

## MODIFIED Requirements

### Requirement: Elegibilidad del cruce por `is_foreign_currency`

El sistema SHALL disparar el cruce automático para todo `pos.payment.method`
con `is_foreign_currency=True`, `type != 'pay_later'`, ambos diarios de cruce
(`cross_account_journal` y `cross_journal`) configurados y una cuenta
transitoria resoluble. El sistema SHALL NOT requerir ningún interruptor
adicional: el campo `apply_one_cross_move` queda eliminado del modelo, de la
vista y de `_load_pos_data_fields`.

Un método que no cumpla alguna de esas condiciones SHALL omitirse en silencio,
sin lanzar excepción. Las cuentas que el cruce va a usar NO son condición de
elegibilidad, salvo las transitorias del cruce entre transitorias
(`use_suspense=True`): si falta una, el método SHALL omitirse sin lanzar
excepción y SHALL dejar un aviso en el log con el método, la sesión y las
cuentas que faltan.

#### Scenario: Método en divisa con ambos diarios configurados

- **GIVEN** un método de pago con `is_foreign_currency=True` y
  `cross_account_journal` + `cross_journal` configurados
- **WHEN** se cierra la sesión con pagos de ese método
- **THEN** se crean los asientos de cruce correspondientes, sin depender de
  ningún otro flag

#### Scenario: Método que no es en divisa

- **GIVEN** un método de pago con `is_foreign_currency=False` y ambos diarios
  de cruce configurados
- **WHEN** se cierra la sesión con pagos de ese método
- **THEN** no se crea ningún asiento de cruce

#### Scenario: Falta un diario de cruce

- **GIVEN** un método con `is_foreign_currency=True` pero solo uno de
  `cross_account_journal`/`cross_journal` configurado
- **WHEN** se cierra la sesión
- **THEN** no se crea ningún asiento de cruce y no se lanza ninguna excepción

#### Scenario: Método de tipo `pay_later`

- **GIVEN** un método `pay_later` con `is_foreign_currency=True` y ambos
  diarios de cruce configurados
- **WHEN** se evalúa su elegibilidad
- **THEN** el método queda excluido por su tipo, aunque el fallback de cuenta
  transitoria sí resolvería una cuenta

#### Scenario: Cierre sin cuenta transitoria

- **GIVEN** una sesión abierta con ventas en un método de efectivo con cruce y
  su `cross_journal` sin cuenta transitoria
- **WHEN** se cierra la sesión
- **THEN** la sesión cierra, no se crea el cruce de ese método y queda un
  aviso en el log

## ADDED Requirements

### Requirement: La sesión no abre si al cruce le faltan sus cuentas

Antes de crear una sesión, el sistema SHALL comprobar, para cada método de pago
elegible para el cruce, que existan las cuentas que el cruce de sus ventas va a
usar, según el tipo de método: en banco, las de las líneas de pago entrantes y
salientes del `cross_journal`; en efectivo (cruce entre transitorias), la
`suspense_account_id` del diario del método y la del `cross_journal`. Un módulo
que cruce un método por otro camino SHALL añadir las cuentas que ese camino usa
(`binaural_pos_close` añade las líneas de pago del `cross_journal` del método del
cajón foráneo, que usa la diferencia de apertura y cierre). Si falta alguna, el
sistema SHALL impedir la apertura con un `ValidationError` que nombre el método,
el diario y la cuenta, y SHALL NOT crear la sesión.

#### Scenario: Banco con el diario real sin cuenta en una línea de pago

- **GIVEN** un método de banco con cruce cuyo `cross_journal` no tiene cuenta
  en su línea de pago entrante
- **WHEN** se intenta abrir la caja
- **THEN** se muestra un error que nombra el método, el diario y la "cuenta de
  pagos entrantes" (no la saliente) y no se crea la sesión

#### Scenario: Efectivo sin cuenta transitoria

- **GIVEN** un método de efectivo con cruce cuyo diario o `cross_journal` no
  tiene cuenta transitoria
- **WHEN** se intenta abrir la caja
- **THEN** se muestra un error que nombra solo el diario sin transitoria

#### Scenario: Efectivo sin cuenta en las líneas de pago del diario real

- **GIVEN** un método de efectivo con cruce, sus dos transitorias configuradas
  y el `cross_journal` sin cuenta en sus líneas de pago, sin otro módulo que use
  esas líneas
- **WHEN** se abre la caja
- **THEN** la sesión se crea: la venta en efectivo no usa esas cuentas

#### Scenario: Cuenta que exige otro módulo

- **GIVEN** un módulo que cruza un método por otro camino (p. ej. la
  diferencia del cajón foráneo de `binaural_pos_close`, change
  `binaural-pos-close-cross-accounts-check`) y añade sus cuentas
- **WHEN** falta una de ellas y se intenta abrir la caja
- **THEN** el mismo error las lista junto a las de este módulo

### Requirement: Cruce sin cuenta en una sesión ya creada

El sistema SHALL lanzar un `UserError` legible que liste las cuentas que
faltan cuando una sesión creada antes de vaciar una cuenta llegue a crear un
cruce cuya pata saldría sin cuenta, en vez del error de base de datos
(`account_move_line_check_accountable_required_fields`), y SHALL NOT crear el
asiento.

#### Scenario: Banco con la cuenta vaciada tras abrir la sesión

- **GIVEN** una sesión ya creada con un método de banco con cruce y la cuenta
  de la línea de pago entrante (o saliente) de su `cross_journal` vaciada
  después
- **WHEN** se crea el cruce de un cobro (o de un reembolso)
- **THEN** se lanza un error legible que nombra el diario y no se crea el
  asiento

#### Scenario: Cuentas configuradas

- **GIVEN** las cuentas del cruce configuradas
- **WHEN** se crea el cruce
- **THEN** el asiento es el mismo que antes de este cambio
