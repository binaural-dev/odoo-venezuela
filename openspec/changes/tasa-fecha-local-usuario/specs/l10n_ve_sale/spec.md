## MODIFIED Requirements

### Requirement: Moneda alterna y tasa por defecto en la orden

Toda orden de venta (`sale.order`) DEBE (MUST) inicializar `foreign_currency_id` con la moneda alterna de la compañía (`foreign_currency_id` de `res.company`, de `l10n_ve_rate`) y los campos `foreign_rate` y `foreign_inverse_rate` con el resultado de `compute_rate` de `res.currency.rate` a la fecha actual en la zona horaria del usuario (`fields.Date.context_today`). Fuera de los defaults, la fecha de tasa de la orden la resuelve `_l10n_ve_rate_date()`: `date_order` (Datetime almacenado en UTC) convertido a la fecha local del usuario con `fields.Datetime.context_timestamp`, o la fecha local de hoy si la orden no tiene fecha. Así, una orden registrada después de las 8 pm en Venezuela (UTC-4) no busca la tasa del día siguiente. Los defaults de tasa (`default_rate` y `default_inverse_rate`) usan la moneda alterna de la compañía y, si esta no está configurada, recurren al bolívar (`base.VEF`) como moneda de respaldo; en ese caso `foreign_currency_id` queda vacío.

#### Scenario: Creación de una orden con moneda alterna configurada

- **WHEN** se crea una orden de venta y la compañía tiene moneda alterna configurada
- **THEN** `foreign_currency_id` queda en la moneda alterna de la compañía y `foreign_rate`/`foreign_inverse_rate` toman la tasa vigente devuelta por `compute_rate`

#### Scenario: Creación de una orden sin tasa cargada

- **WHEN** se crea una orden de venta y no existe ninguna tasa en o antes de la fecha de hoy para la moneda de la orden
- **THEN** se lanza el `UserError` de tasa no asignada de `compute_rate` y la orden no se crea (ticket 15923)

#### Scenario: Orden creada después de las 8 pm

- **WHEN** a las 9 pm (hora de Caracas) se crea una orden cuyo `date_order` en UTC ya es el día siguiente, y solo existe la tasa del día local
- **THEN** la orden toma la tasa del día local y no se lanza el `UserError` de tasa no asignada

### Requirement: Recálculo de tasa condicionado por configuración

El cómputo `_compute_rate` de la orden DEBE (MUST) recalcular `foreign_rate` y `foreign_inverse_rate` (vía `compute_rate` de `l10n_ve_rate`) cuando cambian `foreign_currency_id` o `date_order`, buscando la tasa a la fecha local de `date_order` (`_l10n_ve_rate_date()`), EXCEPTO cuando: (a) la orden tiene `manually_set_rate` activo, (b) la orden proviene del sitio web (`website_id` establecido), o (c) la compañía tiene `update_sale_order_rate_using_date_order` desactivado y la tasa ya es distinta de cero. El flag `update_sale_order_rate_using_date_order` es configurable por compañía desde ajustes (related en `res.config.settings` con `readonly=False`).

#### Scenario: Cambio de fecha con actualización habilitada

- **WHEN** cambia `date_order` de una orden sin tasa manual y la compañía tiene `update_sale_order_rate_using_date_order` activo
- **THEN** `foreign_rate` y `foreign_inverse_rate` se recalculan con la tasa vigente a la nueva fecha

#### Scenario: Cambio de fecha con actualización deshabilitada y tasa ya fijada

- **WHEN** cambia `date_order` y la compañía tiene `update_sale_order_rate_using_date_order` desactivado con `foreign_rate` distinto de cero
- **THEN** la tasa de la orden no se modifica

#### Scenario: Orden con tasa manual

- **WHEN** la orden tiene `manually_set_rate` activo
- **THEN** el recálculo automático no toca sus tasas

### Requirement: Confirmación requiere tasa de moneda alterna

Al confirmar (`action_confirm`), si la orden tiene moneda alterna (`foreign_currency_id`), no tiene `manually_set_rate` activo, y `foreign_rate` es cero, el sistema DEBE (MUST) invocar `compute_rate` con `raise_if_not_found=True` a la fecha local de la orden (`_l10n_ve_rate_date()`), bloqueando la confirmación con un `UserError` en vez de dejar pasar la orden con `foreign_rate` en cero. Desde el ticket 15923 `compute_rate` lanza ese error por defecto, de modo que también los defaults y el `_compute_rate` de la orden fallan sin tasa; aquí se mantiene el argumento explícito por claridad.

#### Scenario: Confirmación sin tasa configurada

- **WHEN** se confirma una orden con moneda alterna, sin `manually_set_rate`, y no existe ninguna tasa registrada para su fecha
- **THEN** se lanza un `UserError` y la orden no se confirma

#### Scenario: Confirmación con tasa manual en cero

- **WHEN** se confirma una orden con `manually_set_rate` activo, aunque `foreign_rate` sea cero
- **THEN** la confirmación no se bloquea por este requirement — la tasa es responsabilidad explícita del usuario

#### Scenario: Confirmación después de las 8 pm

- **WHEN** a las 9 pm (hora de Caracas) se confirma una orden y solo existe la tasa del día local
- **THEN** la orden se confirma con la tasa del día local, sin buscar la del día siguiente en UTC
