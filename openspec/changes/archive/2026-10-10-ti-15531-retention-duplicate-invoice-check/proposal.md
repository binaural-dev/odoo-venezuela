## Why

Una factura consolidada en otro comprobante de retención podía emitirse dos veces si su retención individual seguía en borrador (ticket #15531, caso #94).

## What Changes

- `l10n_ve_payment_extension`: `_check_duplicate_invoices_all_states` en `action_post`, antes de las validaciones por concepto/alícuota/actividad; bloquea si la factura está en otro comprobante `draft`/`emitted` del mismo `type_retention` y mismo partner (no bloquea entre terceros distintos). Mensaje en inglés con traducción en `es_VE.po`. No se cancelan borradores.
- Bump `l10n_ve_payment_extension` 19.0.2.0.35 → 19.0.2.0.36.

## Impact

- Specs: `l10n_ve_payment_extension`.
- Tests: `test_retention_consolidated_duplicates.py`; se ajustaron 3 tests cruzados de `test_retention_ti14548_rules.py` al mensaje nuevo.
