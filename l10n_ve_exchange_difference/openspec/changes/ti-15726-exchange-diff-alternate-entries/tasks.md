## 1. Implementación

- [x] 1.1 `_skip_foreign_compute` y `_zero_foreign_amounts_on_exchange_notes` en `models/account_move_line.py`.
- [x] 1.2 `_check_draftable` en `models/account_move.py`.
- [x] 1.3 Sin migración (fix hacia adelante; las ND/NC ya emitidas se corrigen a mano si se reportan).
- [x] 1.4 Traducciones `es_VE` y bump de versión.

## 2. Tests

- [x] 2.1 `tests/test_exchange_note_foreign_and_draft.py` (montos en 0, recompute, no volver a borrador, factura normal sí).

## 3. Verificación manual

- [ ] 3.1 Emitir una ND de diferencial y verificar que sus apuntes quedan con los tres montos alternos en 0.0.
