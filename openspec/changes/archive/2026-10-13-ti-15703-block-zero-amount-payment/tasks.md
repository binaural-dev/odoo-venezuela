## 1. l10n_ve_accountant — bloquear confirmación de pagos en 0.0

- [x] 1.1 `AccountPayment.action_post()`: `UserError` si `currency_id.is_zero(amount)`, antes de `super()`; se exime con contexto `from_pos` (cierre de sesión POS con neto 0)
- [x] 1.2 Mensaje con la moneda y la unidad mínima (importe convertido redondeado a cero) + traducción es_VE

## 2. Manifest y tests

- [x] 2.1 Bump `l10n_ve_accountant` 19.0.1.0.33 → 19.0.1.0.34
- [x] 2.2 Tests `test_post_zero_amount_raises`, `test_post_positive_amount_ok` y `test_post_zero_amount_from_pos_is_exempt` (`l10n_ve_accountant/tests/test_payment_zero_amount.py`)
- [x] 2.3 Test del wizard `account.payment.register` con diario USD + IGTF y factura en Bs < 0,01 USD (`l10n_ve_igtf/tests/test_igtf_zero_amount_payment.py`): `UserError`, sin pagos creados ni conciliados, factura con su saldo

## 3. Verificación

- [x] 3.1 BD nueva sin demo, addons-path con `ent_tmp`, contenedor `proj`:
  `odoo -c /etc/odoo/odoo.conf -d <db_nueva> -i l10n_ve_igtf --without-demo=true --test-tags /l10n_ve_igtf:TestIgtfZeroAmountPayment,/l10n_ve_accountant:TestPaymentZeroAmount --stop-after-init -p 8099 --gevent-port 8098 --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/home/odoo/src/ent_tmp,/home/odoo/src/third-party-addons,/home/odoo/src/odoo-venezuela`
  Resultado: 4 post-tests, 0 failed, 0 errors (módulos: `l10n_ve_accountant`, `l10n_ve_igtf`).
