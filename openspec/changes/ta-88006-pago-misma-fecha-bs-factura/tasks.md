## 1. l10n_ve_igtf — pago del mismo día

- [x] 1.1 `account_payment.py`: `_same_date_payment_covers_residual` y su uso en `_prepare_move_line_default_vals` y `_fix_writeoff_balance` (solo el mismo día de la factura)
- [x] 1.2 `account_payment.py`: rama IGTF con write-off usa `base_residual`; monto en divisa de la línea de IGTF saliente se suma
- [x] 1.3 `account_move.py` (`l10n_ve_igtf` y `l10n_ve_igtf_note_debit`): `_igtf_base_is_computable` reemplaza la compuerta por `payment_state`
- [x] 1.4 Versiones de los manifests

## 2. Pruebas (Form)

- [x] 2.1 `test_igtf_same_date_payment_balance.py`: 21 casos × 2 redondeos × IVA incluido/excluido × ventas/compras (168), fechas distintas (A04/A05) e IGTF+write-off con fechas distintas (C04x/C05x)
- [x] 2.2 `test_igtf_bi_igtf_payment_state_order.py`: `payment_state` desactualizado conserva la base; revertida y borrador siguen en 0

## 3. Verificación

- [x] 3.1 Las pruebas nuevas fallan en el código anterior y pasan con el cambio
- [x] 3.2 Suite `l10n_ve_igtf` con las semillas de hash 1 a 4: 163 pruebas, 0 fallas
- [x] 3.3 `l10n_ve_igtf_note_debit`: 57 pruebas, 0 fallas
- [x] 3.4 Matriz de 204 resultados contra el código anterior: cambian 8 (IVA3 ×4 objetivo; COM/VEN-C04x y C05x por la corrección del write-off)
- [ ] 3.5 Revisar en el wizard real (staging): COM/VEN-E01 con pago en USD el mismo día
