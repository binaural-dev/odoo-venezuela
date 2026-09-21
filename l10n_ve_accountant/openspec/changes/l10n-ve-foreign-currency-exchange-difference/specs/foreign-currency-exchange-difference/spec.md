# Spec delta: foreign-currency-exchange-difference

## ADDED Requirements

### Requirement: Un toggle de empresa activa el diferencial cambiario alterno

`res.company` SHALL exponer `l10n_ve_use_foreign_exchange_diff` (booleano,
por defecto `False`). Mientras esté activo, el sistema SHALL exigir
configuradas las mismas cuentas y diario que el diferencial cambiario nativo
de Odoo (`income_currency_exchange_account_id`,
`expense_currency_exchange_account_id`, `currency_exchange_journal_id`) — y
SHALL bloquear la activación con un error claro si falta alguna.

#### Scenario: Activar el toggle sin cuentas nativas configuradas

- **GIVEN** una compañía sin `currency_exchange_journal_id` configurado
- **WHEN** se activa `l10n_ve_use_foreign_exchange_diff`
- **THEN** el sistema SHALL lanzar un error explicando qué configurar
- **AND** SHALL NOT permitir guardar el cambio

#### Scenario: Toggle desactivado no genera ningún asiento

- **GIVEN** una compañía con `l10n_ve_use_foreign_exchange_diff` en `False`
- **AND** una factura en VEF cuya tasa cambió entre reserva y pago
- **WHEN** se concilia la factura con su pago
- **THEN** el sistema SHALL NOT calcular ni crear ningún asiento de
  diferencial alterno

### Requirement: El diferencial alterno se inyecta en el MISMO asiento nativo cuando Odoo ya corrige VEF

Cuando `account.move.line._prepare_reconciliation_single_partial` (core)
construye un asiento de diferencial cambiario nativo para un partial, el
sistema SHALL inyectar `foreign_debit`/`foreign_credit` en las MISMAS dos
líneas que el core ya generó, derivando el monto base del `debit`/`credit`
(o `amount_currency`, cuando el core resuelve por la rama
`amount_residual_currency`) que el propio core calculó para esa línea. El
sistema SHALL NOT crear un asiento separado cuando el nativo ya existe.

Motivo: recalcular el monto liquidado de forma independiente (por ejemplo,
comparando `amount_residual` antes/después) da un valor distinto de cero
para AMBOS lados de cualquier conciliación ordinaria, no solo para el lado
que de verdad necesita una corrección de moneda — reusar el valor que el
propio core ya resolvió por pareja evita atribuir el ajuste al lado
equivocado.

#### Scenario: Factura en USD pagada en USD a otra tasa

- **GIVEN** una factura de 100 USD reservada a 40 VEF por USD (4.000 VEF)
- **AND** un pago de 100 USD hecho cuando la tasa es 50 VEF por USD
- **WHEN** se concilian factura y pago
- **THEN** el core SHALL crear su asiento nativo de 1.000 VEF (5.000 − 4.000)
- **AND** ese MISMO asiento SHALL llevar el monto alterno correspondiente si
  corresponde (ver el requirement de exclusión más abajo — en este caso
  concreto, al estar la factura ya en USD, el monto alterno SHALL ser cero)
- **AND** el sistema SHALL NOT crear ningún asiento adicional

#### Scenario: Factura en VEF con residual en VEF que Odoo corrige

- **GIVEN** una factura en VEF reservada a una tasa
- **AND** un pago cuyo monto en VEF deja un residual que Odoo SÍ corrige
  nativamente
- **WHEN** se concilian factura y pago
- **THEN** el asiento nativo de Odoo SHALL llevar también el monto alterno
  calculado sobre el monto de VEF que el propio core está corrigiendo

### Requirement: Un asiento standalone cubre el caso en que solo hay diferencia en la moneda alterna

Cuando el core NO construye ningún asiento nativo para un partial (la moneda
de compañía cuadra exacto) pero sí existe una diferencia real en la moneda
alterna, el sistema SHALL crear un asiento con la MISMA forma que el nativo
(mismo diario, mismas cuentas de ganancia/pérdida cambiaria) con los montos
en moneda de compañía en cero y solo `foreign_debit`/`foreign_credit`
distintos de cero.

#### Scenario: Factura en VEF pagada en VEF exacto a otra tasa

- **GIVEN** una factura de 100 VEF reservada a 40 VEF por USD (2,50 USD)
- **AND** un pago de exactamente 100 VEF hecho cuando la tasa es 50 VEF por
  USD (2,00 USD)
- **WHEN** se concilian factura y pago
- **THEN** el core SHALL NOT crear ningún asiento nativo (VEF cuadra exacto)
- **AND** el sistema SHALL crear un asiento standalone con 0,00 en VEF y
  0,50 USD de pérdida cambiaria alterna

#### Scenario: Sin cambio de tasa entre reserva y pago

- **GIVEN** una factura en VEF pagada sin que la tasa se haya movido desde
  su reserva
- **WHEN** se concilian factura y pago
- **THEN** el sistema SHALL NOT crear ningún asiento, ni nativo ni standalone

### Requirement: Ninguna factura denominada en la moneda alterna genera diferencial alterno

Cuando la línea que fija la tasa de referencia del partial (el lado factura)
está denominada EN `company.foreign_currency_id`, el sistema SHALL NOT
inyectar ni crear ningún monto de diferencial alterno para ese partial, sin
importar cuánto diferencial NATIVO en moneda de compañía se genere ni en qué
moneda se haya pagado.

Motivo: cuando la factura ya está en la moneda alterna, su exposición en esa
moneda es fija y exacta desde el origen (`amount_currency`) — el diferencial
nativo en VEF que sí puede dispararse es un artefacto de medir valor en una
moneda que se devaluó, no un cambio real en la deuda denominada en la moneda
alterna. Calcular un monto alterno igualmente (multiplicando el delta de VEF
por la diferencia de tasas) produce un valor ficticio que descuadra el total
en la moneda alterna.

#### Scenario: Factura en USD pagada en USD — el caso que expuso el bug

- **GIVEN** una factura de 100 USD reservada a 40 VEF por USD
- **AND** un pago de 100 USD hecho a 50 VEF por USD
- **WHEN** se concilian factura y pago
- **THEN** el core SHALL crear su asiento nativo de 1.000 VEF
- **AND** ese asiento SHALL llevar `foreign_debit`/`foreign_credit` en 0,00
  en ambas líneas
- **AND** `l10n_ve_exchange_foreign_diff_entry` SHALL ser `False` en ese
  asiento
- **AND** el sistema SHALL NOT crear ningún asiento standalone adicional

#### Scenario: Factura en USD, cuota pagada en VEF efectivo

- **GIVEN** una factura de 300 USD reservada a 40 VEF por USD, con una cuota
  de 100 USD pagada en VEF EFECTIVO (6.000 VEF, a 60 VEF por USD)
- **WHEN** se concilia esa cuota
- **THEN** el core SHALL crear su asiento nativo de 2.000 VEF (6.000 − 4.000)
- **AND** ese asiento SHALL llevar `foreign_debit`/`foreign_credit` en 0,00,
  porque el pago en VEF ya se traduce nativamente a exactamente 100 USD
  (6.000 ÷ 60) — el mismo monto que la factura ya tenía fijado para esa cuota

#### Scenario: Factura en VEF — el diferencial alterno SÍ aplica

- **GIVEN** una factura en VEF (no en la moneda alterna)
- **AND** una diferencia real entre la tasa de reserva y la tasa de
  liquidación
- **WHEN** se concilia la factura con su pago
- **THEN** el sistema SHALL calcular y registrar el diferencial alterno
  normalmente (este requirement no aplica a facturas en moneda de compañía)

### Requirement: La reversión es 100% nativa vía `exchange_move_id`

Tanto el caso combinado como el standalone SHALL registrar el asiento
creado en `account.partial.reconcile.exchange_move_id` del partial
correspondiente — el mismo campo que Odoo usa para sus propios asientos
genéricos. El sistema SHALL NOT implementar lógica propia de reversión ni
una clave de idempotencia propia.

#### Scenario: Deshacer una conciliación con asiento nativo combinado

- **GIVEN** un partial cuyo `exchange_move_id` es un asiento que lleva monto
  nativo y alterno juntos
- **WHEN** se deshace la conciliación (`remove_move_reconcile`)
- **THEN** Odoo SHALL revertir automáticamente ese asiento (mecanismo core),
  sin intervención de código propio

#### Scenario: Deshacer una conciliación con asiento standalone

- **GIVEN** un partial cuyo `exchange_move_id` es un asiento standalone
  (solo alterno)
- **WHEN** se deshace la conciliación
- **THEN** Odoo SHALL revertir ese asiento automáticamente de la misma forma

#### Scenario: Reprocesar la misma conciliación no duplica el asiento

- **GIVEN** un partial cuyo `exchange_move_id` ya apunta a un asiento
  standalone
- **WHEN** el mismo cálculo se dispara de nuevo sobre ese partial
- **THEN** el sistema SHALL reutilizar el `exchange_move_id` existente
- **AND** SHALL NOT crear un segundo asiento

### Requirement: Se honra la supresión nativa del cálculo de diferencial

Cuando el contexto `no_exchange_difference` o
`no_exchange_difference_no_recursive` está activo (usado por el propio core
para suprimir su lógica de diferencial, p. ej. al cerrar la línea receivable
del propio asiento de diferencial), el sistema SHALL NOT calcular ni crear
ningún asiento de diferencial alterno.

#### Scenario: Conciliación bajo contexto de supresión

- **GIVEN** una factura y un pago con diferencia de tasa
- **WHEN** se concilian con `no_exchange_difference=True` en el contexto
- **THEN** el sistema SHALL NOT crear ningún asiento de diferencial alterno,
  aunque exista una diferencia real de tasa
