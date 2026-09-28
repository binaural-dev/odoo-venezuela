## 1. Validación en `l10n_ve_invoice`

- [x] 1.1 Quitar `@api.constrains("invoice_line_ids")` de `_check_refund_against_origin` (`models/account_move.py`) y llamarlo desde `_post()` sobre `draft_moves`, antes de `super()._post()`.
- [x] 1.2 Agregar el hook `_l10n_ve_skip_refund_origin_validation()` (por registro, por defecto la clave de contexto) y usarlo dentro del loop en vez del `return` temprano por contexto.
- [x] 1.3 NC hermanas: dominio `state = posted` o `id in self.ids`, en vez de `state != cancel`.
- [x] 1.4 Eliminar `_check_refund_line_against_origin` (`models/account_move_line.py`).
- [x] 1.5 Bump de manifest `19.0.1.0.19` -> `19.0.1.0.20`.
- [x] 1.6 Sin cambios en `i18n/es_VE.po`: los mensajes de error no cambian.

## 2. Tests

- [x] 2.1 `tests/test_refund_origin_validation.py`: todas las aserciones de `ValidationError` pasan de `create()`/`write()` a `_post()`; los casos permitidos verifican `state == 'posted'`.
- [x] 2.2 Nuevos: `test_second_credit_note_from_reversal_wizard_is_editable_before_posting`, `test_forgotten_draft_credit_note_does_not_block_posting_another`, `test_credit_notes_posted_together_cannot_jointly_exceed_origin_amount`, `test_line_write_over_cap_is_only_blocked_at_posting`.
- [x] 2.3 `test_credit_note_line_without_product_is_blocked`: pasaba por `_check_product_id` de `l10n_ve_accountant`, no por esta validación. Ahora quita el producto con un `write()` de línea y verifica el mensaje "must have a product" al publicar.

## 3. Verificación

- [x] 3.1 Tests de `l10n_ve_invoice`, `l10n_ve_donation`, `l10n_ve_exchange_difference` y `l10n_ve_igtf_note_debit` en una base nueva: 347 tests, 7 fallos -- los mismos 7 que ya fallaban sin este cambio (`payment_state` / conciliación en exchange_difference e igtf_note_debit), ninguno nuevo.
- [x] 3.2 Manual en la BD de desarrollo: INV/2026/0016 con una NC parcial publicada -> "Revertir" crea el borrador completo; publicarlo sin reducir falla; reducido a 2 u se publica.
- [x] 3.3 Prueba funcional de la NC de donación (publicada a mano tras el wizard de alerta): OK.
