# Spec delta: pos-cross-account-move

## ADDED Requirements

### Requirement: El cruce de ventas apunta a la Cuenta Transitoria del `cross_journal`

El sistema SHALL hacer que **el asiento de cruce de ventas** acredite/debite
`cross_journal.suspense_account_id` (la Cuenta Transitoria del diario de cruce) en
la pata del `cross_journal`, en vez de su cuenta de liquidez confirmada
(`inbound/outbound_payment_method_line_ids.payment_account_id`) — la misma cuenta a
la que ya apunta el cruce de entradas/salidas de efectivo (`use_suspense=True`).
Este comportamiento es **único, no configurable**: no existe ningún flag que lo
active o desactive.

`_get_cross_real_account`, `_line_vals_move_cross_incoming`/`_outgoing` y
`_create_cross_move_for` SHALL aceptar un parámetro `real_to_suspense` (default
`False`). Con `real_to_suspense=True` y `use_suspense=False`:

- `_get_cross_real_account` SHALL devolver `cross_journal.suspense_account_id`.
- `_get_cross_transitory_account` (la pata de **origen**) SHALL NOT cambiar: sigue
  devolviendo `journal_id.default_account_id` (cash) u `outstanding_account_id`
  (bank), porque el nativo deja ahí el dinero de la venta.
- `_create_cross_move_for` SHALL NOT invertir la dirección entrante/saliente ni la
  polaridad débito/crédito: esa inversión sigue gobernada únicamente por
  `use_suspense`, no por `real_to_suspense`.

El sistema SHALL pasar `real_to_suspense=True` desde `_validate_cross_move` (ventas)
en ambas granularidades (split y combine). El parámetro es el único discriminador
frente a los demás llamadores de `use_suspense=False`: las diferencias de
apertura/cierre de `binaural_pos_close` (`_post_foreign_statement_difference`)
SHALL NOT pasarlo, de modo que su cuenta destino no cambia. Cuando `use_suspense=True`
(cash in/out), `real_to_suspense` es indiferente porque esa rama ya devuelve la
suspense.

#### Scenario: Venta en efectivo foráneo

- **GIVEN** un método `cash` elegible con `is_foreign_currency=True` y ambos diarios
  de cruce configurados
- **WHEN** se cierra la sesión con un pago de venta de ese método
- **THEN** el asiento de cruce acredita `cross_journal.suspense_account_id` (destino)
  y debita `journal_id.default_account_id` (origen), con la polaridad normal de una
  venta — solo cambió la cuenta destino frente al comportamiento previo (liquidez
  confirmada)

#### Scenario: Las diferencias de apertura/cierre no se ven afectadas

- **GIVEN** una diferencia de cierre foránea que dispara su propio cruce vía
  `_post_foreign_statement_difference`
- **WHEN** se cierra la sesión
- **THEN** el asiento de cruce de la diferencia sigue apuntando a su cuenta destino
  actual (liquidez confirmada), porque ese llamador no pasa `real_to_suspense`

#### Scenario: Coincidencia de cuenta destino entre ventas y cash in/out

- **GIVEN** una venta en efectivo foráneo y una entrada de efectivo en la misma
  sesión, sobre un método con cruce configurado
- **WHEN** se cierra la sesión
- **THEN** el cruce de la venta y el de la entrada de efectivo mueven la **misma**
  cuenta `cross_journal.suspense_account_id`, de modo que ambos quedan acumulados en
  la misma cuenta transitoria pendiente de conciliación bancaria
