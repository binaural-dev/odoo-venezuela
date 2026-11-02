# Fix: orden estable del libro de ventas dentro de un mismo día

## Why

Ticket Helpdesk #16159 (https://binaural.odoo.com/odoo/all-tickets/16159), antes reportado en
#15956 (https://binaural.odoo.com/odoo/all-tickets/15956) por Jumpi Rides.

`search_moves()` ordenaba solo por `invoice_date_display`, que es un campo `Date`, sin otro criterio.
Las facturas de un mismo día salían en el orden físico de la tabla: cada vez que se modifica una
factura (pago, digitalización) PostgreSQL guarda la versión nueva de la fila al final, así que las
facturas tocadas después de publicarse se iban al final del día y el orden cambiaba de una
generación a otra.

En staging se resolvió con el módulo de cliente `jumpi_rides_l10n_ve_fix` (verificado en septiembre
y octubre de 2026); este cambio lo lleva a la localización.

## What Changes

- `wizard.accounting.reports._get_book_order()`: en el libro de ventas,
  `invoice_date_display, invoice_date_display_datetime, id`; el de compras sigue en
  `invoice_date_display`. `search_moves()` lo usa.
- `l10n_ve_iot_mf`: su `search_moves()` sin máquina fiscal usa el mismo `_get_book_order()`.
- Bump de versión: `l10n_ve_invoice` `19.0.1.0.28`, `l10n_ve_iot_mf` `19.0.1.0.4`.

## Decisiones

- **El desempate es la fecha-hora de registro, como en el módulo de staging.** Depende del fix de
  #15954 (`l10n_ve_invoice` `19.0.1.0.27`), que guarda esa hora con el día correcto después de las
  20:00.
- **El orden se hace en el SQL, no en Python.** `search()` ya devuelve los documentos ordenados y
  los módulos que heredan `search_moves()` (`l10n_ve_payment_extension`,
  `binaural_third_party_invoice`) lo reciben así.
- **El libro de compras no cambia.**

## Observaciones

- En una factura con fecha anterior al día en que se registró, el campo guarda la fecha de la
  factura con la hora del registro: TERC-0264, con fecha 14/10 y registrada el 19/10, se ordena como
  el 14/10 a las 11:42 am.
- Un borrador creado antes que otras facturas del día y publicado después conserva la fecha-hora de
  su creación, así que sale antes que ellas aunque su número sea mayor.

## Non-goals

- `l10n_ve_account_mf` reordena en Python solo por fecha en sus modos de máquina fiscal; no se
  modifica.

## Tests

`l10n_ve_invoice/tests/test_accounting_reports.py`:
`test_search_moves_sale_same_day_edited_after_post`,
`test_search_moves_sale_same_day_by_registration_time` y `test_book_order_purchase_unchanged`.
