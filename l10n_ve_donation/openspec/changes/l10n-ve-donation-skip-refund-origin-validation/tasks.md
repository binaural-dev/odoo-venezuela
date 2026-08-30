## 1. Bypass de la validación de origen

- [x] 1.1 Agregar `l10n_ve_skip_refund_origin_validation=True` al `with_context()` del `create()` de la Nota de Crédito en `_reverse_moves()` (`models/account_move.py`). Verificado leyendo el diff.
- [x] 1.2 Bump de manifest `19.0.2.0.2` -> `19.0.2.0.3`.

## 2. Tests

- [x] 2.1 Crear `tests/` (el módulo no tenía) con `test_donation_credit_note_regression.py`: confirma que la reversión automática crea la NC con el producto de donación (corrección), y que la misma NC sin el bypass es rechazada por `l10n_ve_invoice` (reproduce la regresión).

## 3. Verificación manual

- [ ] 3.1 Revertir una factura marcada como donación en un ambiente Odoo 19 con `l10n_ve_invoice` actualizado y confirmar que la Nota de Crédito se crea sin `ValidationError`.
