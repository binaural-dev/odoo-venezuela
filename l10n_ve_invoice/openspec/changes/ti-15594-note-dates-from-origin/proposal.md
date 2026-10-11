# Fix: NC y ND respetan la fecha de su factura origen

## Why

Ticket Helpdesk #15594 (https://binaural.odoo.com/odoo/helpdesk/action-389/15594).
Era posible confirmar una NC o ND con fecha anterior a la de la factura origen.

## Regla

La nota (NC o ND) es la misma transacción que su origen:

- `invoice_date` (fecha de tasa): siempre igual a la del origen (solo lectura en el formulario de la nota).
- `invoice_date_display` (fecha del documento): editable, por defecto hoy (`context_today`),
  nunca anterior a la fecha del origen ni posterior a hoy.
- Una sola factura por nota.

## What Changes

- `account.debit.note` (`models/account_debit_note.py`): `_prepare_default_values` toma
  `invoice_date_display` del wizard e `invoice_date` del origen; `create_debit` valida
  `_l10n_ve_check_note_date`; `default_get` y `create_debit` rechazan más de un documento.
- `account.move._check_dates_not_in_future` (en `action_post`): una nota con
  `invoice_date_display` anterior al origen no se confirma (cubre ediciones posteriores
  a la creación desde el formulario).
- La fecha del wizard queda editable (sin vista que la bloquee).
- La fecha de la ND de IGTF no cambia (hoy); su exención del guard de fecha futura
  (`l10n_ve_skip_future_date_check` + `_l10n_ve_allows_future_date`) aplica solo a notas automáticas.
- La NC se resuelve en `l10n_ve_accountant` (change homónimo).

## Non-goals

- `l10n_ve_out_of_fiscal_period_warning` se conserva sin cambios.
