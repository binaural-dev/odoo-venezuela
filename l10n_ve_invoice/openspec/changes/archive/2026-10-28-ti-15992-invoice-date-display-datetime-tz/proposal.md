# Fix: fecha-hora de emisión con día y hora de la misma zona horaria

## Why

Ticket Helpdesk #15992 (https://binaural.odoo.com/odoo/helpdesk/action-389/15992), reportado por
Jumpi Rides.

`invoice_date_display_datetime` se armaba con `fields.Datetime.now()`, que está en UTC, y se le
cambiaba el día por el de `invoice_date_display`, que es una fecha local (`context_today`). Desde
las 20:00 en Venezuela (UTC-4) la hora UTC ya es del día siguiente, así que el campo quedaba en el
día anterior. El libro de ventas y la factura digital de TFHKA toman la fecha-hora de este campo.

`invoice_date_display` ya está bien: su default es `context_today` y `l10n_ve_base` da default a la
zona horaria de los usuarios (TI-15211). Solo falla la conversión a fecha-hora.

En staging se resolvió con el módulo de cliente `jumpi_rides_l10n_ve_fix`; este cambio lo lleva a
la localización, sobre `maintenance-19.0`.

## What Changes

- `account.move._get_invoice_date_display_datetime(date_value)`: fecha (o `context_today` si no
  hay) con la hora local de `context_timestamp`, guardada en UTC naive. `create()` (vals y bucle de
  `moves`) y `write()` lo usan en lugar de `now.replace(day=...)`.
- `write()` solo renueva la hora de los documentos cuya `invoice_date_display` cambia.
- `post_init_hook`: mismo método, por compañía y fecha, con la zona horaria de la compañía, en
  lugar de `NOW()`.
- Migración `19.0.1.0.27` (`post-10`): por compañía, corrige los documentos cuyo día local no
  coincide con `invoice_date_display`, conservando la hora local.
- Bump de versión `19.0.1.0.27` (una sobre `maintenance-19.0`).

## Decisiones

- **Día y hora de la misma zona horaria, la del usuario.** `context_today` y `context_timestamp`
  leen la misma zona horaria, así que fecha y hora no pueden quedar desfasadas. Con eso deja de
  importar la compañía de los vals en `create()` o de los documentos en `write()`.
- **La migración y el hook usan la zona horaria de la compañía.** No se conoce el usuario que
  registró cada documento; la de la compañía es la que `l10n_ve_base` da por defecto a los usuarios.
- **El orden del libro (#15994) va en un PR aparte.**

## Non-goals

- Desempate por fecha-hora e `id` en `search_moves()` (HD #15994).
- `l10n_ve_iot_mf` y `l10n_ve_account_mf` tienen su propio orden del libro y no se modifican.

## Tests

`l10n_ve_invoice/tests/test_invoice_date_display_datetime.py`, con la hora congelada en
2026-09-15 02:30 UTC (14/09 22:30 en Caracas): usuario con zona horaria, sin zona horaria, fecha
retroactiva, sin fecha, `create()`, `write()` con y sin cambio de fecha, fecha vacía y
`post_init_hook`.
