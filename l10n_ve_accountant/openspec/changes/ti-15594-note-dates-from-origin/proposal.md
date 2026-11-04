# Fix: la NC respeta la fecha de su factura origen

## Why

Ticket Helpdesk #15594 (https://binaural.odoo.com/odoo/helpdesk/action-389/15594).
Ver el change homónimo en `l10n_ve_invoice`.

## Regla

La nota (NC o ND) es la misma transacción que su origen:

- `invoice_date` (fecha de tasa): siempre igual a la del origen (solo lectura en el formulario de la nota).
- `invoice_date_display` (fecha del documento): editable, por defecto hoy (`context_today`),
  nunca anterior a la fecha del origen ni posterior a hoy.
- Una sola factura por nota.

## What Changes

- `account.move` (`models/account_move.py`): `_l10n_ve_check_note_date(note_date)` valida
  origen <= fecha <= hoy (compartido con la ND).
- `account.move.reversal` (`wizard/account_move_reversal.py`): `_prepare_default_reversal`
  fija `invoice_date_display` con la fecha del wizard e `invoice_date` con la del origen;
  `reverse_moves` valida la fecha; `default_get` y `reverse_moves` rechazan más de una factura.
- `views/account_move.xml`: `invoice_date` (tasa) readonly si hay `reversed_entry_id` o
  `debit_origin_id`; `invoice_date_display` sigue editable en borrador.
- Bump `19.0.1.0.29` -> `19.0.1.0.30`.

## Impacto a revisar

- `l10n_ve_igtf_note_debit`, `l10n_ve_donation` y `l10n_ve_igtf` crean notas por código:
  una fecha anterior al origen o futura ahora falla en `reverse_moves`.
- `_get_all_reconciled_invoice_partials` ya no falla con registros sin guardar (NewId).
- `l10n_ve_stock` (`_validate_single_sale_tax`) exime a los productos `combo`, igual que
  `l10n_ve_accountant` (FIX-061) y el núcleo de Odoo 19 (oculta y vacía los impuestos del combo; sus
  impuestos viven en las líneas de los componentes). Con `l10n_ve_stock` instalado, los tests 15, 16 y 20
  de `test_product_template.py` quedan en su versión original. Bump `l10n_ve_stock` `19.0.1.0.8` -> `19.0.1.0.9`.
