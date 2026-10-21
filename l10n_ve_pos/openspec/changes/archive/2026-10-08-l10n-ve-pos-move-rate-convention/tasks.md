# Tasks

## 1. Tests

- [x] 1.1 `tests/test_pos_payment_foreign_rate.py`: motor
      (`_get_move_foreign_rate_vals`), factura y asiento de pago
- [x] 1.2 `l10n_ve_pos_igtf/tests/test_pos_igtf_payment_move_rate.py`: asiento
      de pago con IGTF
- [x] 1.3 Batería e2e de `binaural_pos_multicurrency`:
      `test_move_rate_convention` en las tres cajas

## 2. Corrección

- [x] 2.1 `pos_config.py`: `_get_move_foreign_rate_vals`
- [x] 2.2 `pos_order.py` (`_prepare_invoice_vals`) y `pos_payment.py`
      (`_create_payment_moves`)
- [x] 2.3 `l10n_ve_pos_igtf/models/pos_payment.py`
- [x] 2.4 `binaural_pos_multicurrency` (integra-addons, PR #2896)

## 3. Verificación

- [x] 3.1 Rojo antes del fix (factura y asiento de pago con 36,5 en `foreign_rate`; IGTF igual; capa A: `CVF`/`ALTF` 0,001245 / 0,001245 y `CVV` 0 / 0) y verde después; suites completas en `l10n-ve-pos-payment-foreign-rate` 3.1
- [x] 3.2 Navegador (posv19, sesión 479, venta 000004): INV/2026/0105 y POSS/2026/0148 con 803,34 / 0,001244802947693; alterno igual que antes (11,60 $; 10,00 + 1,60) y sin mensaje de cambio de tasa en el chatter
