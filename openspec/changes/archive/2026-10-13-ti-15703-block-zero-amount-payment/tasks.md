## 1. l10n_ve_accountant — bloquear confirmación de pagos en 0.0

- [x] 1.1 `AccountPayment.action_post()`: `UserError` si `currency_id.is_zero(amount)`, antes de `super()`
- [x] 1.2 Traducción es_VE del mensaje

## 2. Manifest y tests

- [x] 2.1 Bump `l10n_ve_accountant` 19.0.1.0.30 → 19.0.1.0.31
- [x] 2.2 Tests `test_post_zero_amount_raises` y `test_post_positive_amount_ok` (`test_payment_zero_amount.py`)

## 3. Verificación

- [x] 3.1 Tests corridos en aislado, BD nueva sin demo, sobre esta rama — 2 post-tests OK
