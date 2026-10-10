# Fix: la NC hereda las fechas de su factura origen

## Why

Ticket Helpdesk #15594 (https://binaural.odoo.com/odoo/helpdesk/action-389/15594).
Ver el change homónimo en `l10n_ve_invoice`.

## What Changes

- `account.move.reversal` (`wizard/account_move_reversal.py`): `_prepare_default_reversal`
  toma `invoice_date_display`, `invoice_date` y `date` del origen para todo documento
  facturable; `default_get` inicializa `date`; `default_get` y `reverse_moves` rechazan
  más de una factura.
- `wizard/account_move_reversal.xml` (nuevo): `date` siempre de solo lectura.
- `views/account_move.xml`: `invoice_date_display` e `invoice_date` readonly si hay
  `reversed_entry_id` o `debit_origin_id`.
- Bump `19.0.1.0.29` -> `19.0.1.0.30`.

## Impacto a revisar

- `l10n_ve_igtf_note_debit`, `l10n_ve_donation` y `l10n_ve_igtf` crean NC con fecha de hoy;
  ahora quedan con la fecha del origen.
- Reversiones sobre períodos bloqueados heredan la fecha del origen.
- `_get_all_reconciled_invoice_partials` ya no falla con registros sin guardar (NewId): sin id de base de datos devuelve el resultado del núcleo.
