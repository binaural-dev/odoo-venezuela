# Fix: fecha-hora de emisión con la hora local y orden estable del libro de ventas

## Why

Tickets Helpdesk #15992 (https://binaural.odoo.com/odoo/helpdesk/action-389/15992) y #15994
(https://binaural.odoo.com/odoo/helpdesk/action-389/15994), reportados por Jumpi Rides.

- `invoice_date_display_datetime` se armaba con `fields.Datetime.now()`, que está en UTC, y se le
  cambiaba el día por el de `invoice_date_display`, que es una fecha local. Desde las 20:00 en
  Venezuela (UTC-4) la hora UTC ya es del día siguiente, así que el campo quedaba en el día
  anterior. El libro de ventas y la factura digital de TFHKA toman la fecha-hora de este campo.
- `search_moves()` ordenaba solo por `invoice_date_display` (Date), sin desempate: las facturas de
  un mismo día salían en el orden que devolviera PostgreSQL.

En staging se resolvió con el módulo de cliente `jumpi_rides_l10n_ve_fix`; este cambio lo lleva a
la localización.

## What Changes

- `account.move`: `_get_invoice_date_display_tz` (compañía → `America/Caracas`, el mismo respaldo que la migración) y
  `_build_invoice_date_display_datetime` (fecha de la factura + hora local actual, guardado en UTC
  naive). `create()` y `write()` los usan en lugar de `now.replace(day=...)`.
- Migración `19.0.1.0.27` (`post-10`): por compañía, corrige los documentos cuyo día local no
  coincide con `invoice_date_display`, conservando la hora local.
- `wizard.accounting.reports.search_moves()`: orden
  `invoice_date_display, invoice_date_display_datetime, id`.
- `post_init_hook`: completa `invoice_date_display_datetime` con el mismo helper, por compañía y
  fecha, en lugar de `NOW()` (que mezclaba la fecha local con la hora UTC).
- Bump de versión `19.0.1.0.27`.

## Decisiones

- **Zona horaria de la compañía, sin pasar por la del usuario.** El documento fiscal es de la
  compañía, el resultado no depende de quién lo registra y coincide con la migración.
- **La fecha-hora se fija al crear o al cambiar la fecha, no al publicar.** Un borrador creado
  antes y publicado después sale antes en el libro aunque su correlativo sea mayor; queda fijado
  en un test.
- **El desempate se hace en el SQL y aplica a ambos libros.** En compras solo fija el orden de los
  documentos de un mismo día.
- **La migración solo toca los documentos con el día errado.** Los migrados desde v17 (mediodía
  UTC) y los correctos no cambian.

## Non-goals

- `l10n_ve_iot_mf` y `l10n_ve_account_mf` tienen su propio orden del libro y no se modifican.
- `tfhka.service.base._localize` sigue usando la zona horaria del usuario; en Venezuela coincide
  con la de la compañía.

## Tests

`l10n_ve_invoice/tests/test_invoice_date_display_datetime.py` y, para el orden del libro,
`test_search_moves_same_day_ordered_by_datetime` y
`test_search_moves_draft_posted_later_keeps_creation_time` en `test_accounting_reports.py`; además pasan
`test_accounting_reports.py` y `test_ti_15211_invoice_date_timezone.py`.
