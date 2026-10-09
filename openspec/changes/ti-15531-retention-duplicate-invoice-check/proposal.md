## Why

Una factura consolidada en otro comprobante de retención podía emitirse dos veces si su retención individual seguía en borrador (ticket #15531, caso #94). Además, en `l10n_ve_accountant` el widget de pagos buscaba con `NewId` en facturas sin guardar (`Domains don't support NewId`).

## What Changes

- `l10n_ve_payment_extension`: `_check_duplicate_invoices_all_states` en `action_post`, antes de las validaciones por concepto/alícuota/actividad; bloquea si la factura está en otro comprobante `draft`/`emitted` del mismo `type_retention`. Mensaje en inglés con traducción en `es_VE.po`. No se cancelan borradores.
- `l10n_ve_accountant`: `_get_all_reconciled_invoice_partials` usa `_origin.id`; bump 19.0.1.0.29 → 19.0.1.0.30.

## Impact

- Specs: `l10n_ve_payment_extension`, `l10n_ve_accountant`.
- Tests: `test_retention_consolidated_duplicates.py`, `test_reconciled_partials_new_record.py`; se ajustaron 3 tests cruzados de `test_retention_ti14548_rules.py` al mensaje nuevo.
