## 1. Exención por campo

- [x] 1.1 Override de `_l10n_ve_skip_refund_origin_validation()` en `models/account_move.py`: `is_donation or super()`.
- [x] 1.2 Comentario de la clave de contexto en `_reverse_moves()` actualizado (queda redundante).
- [x] 1.3 Bump de manifest `19.0.2.0.4` -> `19.0.2.0.5`.

## 2. Tests

- [x] 2.1 `test_is_donation_exempts_credit_note_from_origin_validation` reemplaza a `test_regression_without_bypass_would_block_the_reversal`.
- [x] 2.2 Nuevo `test_donation_credit_note_posted_later_without_context_key`.

## 3. Verificación

- [x] 3.1 Suite de `l10n_ve_donation` en verde en una base nueva, junto con `l10n_ve_invoice`, `l10n_ve_exchange_difference` y `l10n_ve_igtf_note_debit` (sin fallos nuevos).
- [x] 3.2 Prueba funcional: orden de venta de donación -> factura -> NC en borrador -> Confirmar / Aceptar -> publicada sin error.
