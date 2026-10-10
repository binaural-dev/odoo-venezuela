## 1. Implementación

- [x] 1.1 `_prepare_default_reversal`, `default_get`, `reverse_moves` en `wizard/account_move_reversal.py`.
- [x] 1.2 Vista del wizard y vista del formulario de `account.move`.
- [x] 1.3 Registrar `wizard/account_move_reversal.xml` en el manifest y bump de versión.
- [x] 1.4 `_get_all_reconciled_invoice_partials` (`models/account_move.py`) devuelve el resultado del núcleo sin buscar cuando el registro no está guardado (`self._origin.id` vacío).
- [x] 1.5 Traducción `es_VE` del mensaje de un solo documento.

## 2. Tests

- [x] 2.1 Cubiertos por `l10n_ve_invoice/tests/test_note_dates_from_origin.py`.
- [x] 2.2 `test_foreign_exchange_diff.py`: registro sin guardar en `_get_all_reconciled_invoice_partials`.

## 3. Verificación manual

- [ ] 3.1 Reproducir los pasos del ticket (NC con fecha de reversión un día anterior).
