# Spec delta: pos-self-order-foreign-amount

## ADDED Requirements

### Requirement: `pos.order.foreign_amount_total` siempre tiene un valor al crearse, sin importar el canal

El sistema SHALL completar `foreign_amount_total` (y `foreign_currency_rate`)
con `pos.config._convert`/`_get_pos_conversion_rate` cuando el canal que crea
el `pos.order` no los provee, en vez de depender exclusivamente del patch JS
de la caja normal (`serializeForORM`, cargado solo en el bundle
`point_of_sale._assets_pos`).

#### Scenario: Pedido creado desde el Kiosko/Autopedido

- **GIVEN** un pedido creado a través de `pos_self_order` (Kiosko o
  Autopedido móvil), cuyo payload no incluye `foreign_amount_total` ni
  `foreign_currency_rate` (el bundle del Kiosko no carga el patch JS de
  `l10n_ve_pos`)
- **WHEN** el servidor procesa la creación (`pos.order.create` →
  `_complete_values_from_session`)
- **THEN** `foreign_amount_total` queda en
  `pos.config._convert(amount_total, currency_id, foreign_currency_id)` y
  `foreign_currency_rate` en `pos.config._get_pos_conversion_rate(currency_id,
  foreign_currency_id)`, no en `NULL` — el `INSERT` no falla

#### Scenario: Pedido creado desde la caja normal (comportamiento sin cambios)

- **GIVEN** un pedido creado desde la app de caja normal, cuyo payload SÍ
  incluye `foreign_amount_total`/`foreign_currency_rate` (calculados por el
  patch JS `serializeForORM`)
- **WHEN** el servidor procesa la creación
- **THEN** los valores enviados por el cliente se respetan tal cual —
  `_complete_values_from_session` usa `setdefault`, no pisa un valor ya
  presente

#### Scenario: Compañía sin moneda foránea configurada

- **GIVEN** una compañía cuyo `foreign_currency_id` no está configurado
- **WHEN** se crea un pedido desde cualquier canal sin
  `foreign_amount_total` en el payload
- **THEN** `foreign_amount_total`/`foreign_currency_rate` quedan en `0.0`
  (no se lanza error; `_convert`/`_get_pos_conversion_rate` ya devuelven
  `0.0` cuando no hay conversión posible)

### Requirement: `recompute_prices()` mantiene sincronizado el total foráneo tras el recálculo autoritativo

El sistema SHALL recalcular `foreign_amount_total`/`foreign_currency_rate`
cada vez que `pos_self_order` recalcula `amount_total` de forma autoritativa
contra el catálogo real (`recompute_prices()`), para que el valor
provisional calculado en la creación no quede desactualizado.

#### Scenario: El total local cambia tras `recompute_prices()`

- **GIVEN** un pedido del Kiosko cuyo `amount_total` provisional (enviado
  por el cliente) difiere del total real de las líneas contra el catálogo
- **WHEN** el controlador del Kiosko llama a `order.recompute_prices()`
- **THEN** `foreign_amount_total`/`foreign_currency_rate` se recalculan a
  partir del `amount_total` ya corregido, usando los mismos
  `pos.config._convert`/`_get_pos_conversion_rate`

### Requirement: Los overrides de `recompute_prices` no requieren que `l10n_ve_pos` dependa de `pos_self_order`

El sistema SHALL mantener el override de `recompute_prices()` en un módulo
puente (`l10n_ve_pos_self_order`, `depends=["l10n_ve_pos","pos_self_order"]`,
`auto_install=True`) en vez de en `l10n_ve_pos` directamente, porque ese
método solo existe cuando `pos_self_order` está instalado y la mayoría de
clientes de `l10n_ve_pos` no usan Kiosko.

#### Scenario: Cliente sin `pos_self_order` instalado

- **GIVEN** una base de datos con `l10n_ve_pos` instalado y `pos_self_order`
  NO instalado
- **WHEN** se crea un pedido desde la caja normal
- **THEN** el comportamiento es idéntico al de antes de este change —
  `l10n_ve_pos_self_order` nunca se instala (su dependencia `pos_self_order`
  falta) y no hay ningún override de `recompute_prices()` cargado

#### Scenario: Cliente instala `pos_self_order` sobre una BD con `l10n_ve_pos`

- **GIVEN** una base de datos con `l10n_ve_pos` ya instalado
- **WHEN** se instala `pos_self_order` (manualmente, para activar el Kiosko)
- **THEN** `l10n_ve_pos_self_order` se instala automáticamente
  (`auto_install=True`), sin paso manual adicional
