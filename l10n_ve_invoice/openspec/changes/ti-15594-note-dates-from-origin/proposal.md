# Fix: NC y ND heredan las fechas de su factura origen

## Why

Ticket Helpdesk #15594 (https://binaural.odoo.com/odoo/helpdesk/action-389/15594).
Era posible confirmar una NC o ND con fecha anterior a la de la factura origen,
y la fecha de factura de la nota quedaba distinta a su fecha contable. Una nota
es la misma transacción que su origen y no puede fecharse distinto.

## What Changes

- `account.debit.note` (`models/account_debit_note.py`): `_prepare_default_values`
  toma `invoice_date_display`, `invoice_date` y `date` del origen (cliente y
  proveedor). `default_get` inicializa `date` con la fecha del origen y rechaza
  más de un documento (`UserError`, también en `create_debit`).
- Vista del wizard: `date` siempre de solo lectura. Sin campos nuevos.
- Excepción: el contexto `l10n_ve_note_date` fija `date`, `invoice_date_display` e
  `invoice_date` de la ND (lo usa la ND automática de IGTF, que toma la fecha del pago).
- La NC se resuelve en `l10n_ve_accountant` (ver su change homónimo).
- Se reemplaza el requisito "Preservación de la tasa y de la fecha fiscal propia"
  (la ND ya no declara su propia fecha fiscal).

## Non-goals

- No se agrega constraint que bloquee con error: la nota se crea directamente con
  los valores correctos.
- `l10n_ve_out_of_fiscal_period_warning` se conserva sin cambios (queda inactivo en el flujo normal).
