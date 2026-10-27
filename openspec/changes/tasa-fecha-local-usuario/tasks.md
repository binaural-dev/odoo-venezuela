## 1. l10n_ve_accountant — fecha de respaldo local en asientos y pagos

- [x] 1.1 `account.move`: `default_rate`, `default_inverse_rate`, `create` y `_compute_rate_for_documents` usan `fields.Date.context_today`
- [x] 1.2 `account.payment`: `_compute_rate` y `_compute_other_rate` usan `fields.Date.context_today` como respaldo de `date`
- [x] 1.3 Test unitario `tests/test_rate_date_user_tz.py` (tag `l10n_ve_accountant_rate_tz`): factura en borrador sin fecha a las 9 pm toma la tasa del día local; una `invoice_date` explícita del día siguiente no se corrige

## 2. l10n_ve_sale — fecha local de la orden

- [x] 2.1 `_l10n_ve_rate_date()`: `date_order` convertido a la fecha local del usuario
- [x] 2.2 `create`, `_compute_rate` y la confirmación usan `_l10n_ve_rate_date()`; los defaults de tasa usan `fields.Date.context_today`
- [x] 2.3 Test unitario `tests/test_sale_order_rate_tz.py` (tag `l10n_ve_sale`): orden creada y confirmada a las 9 pm toma la tasa del día local

## 3. Verificación

- [ ] 3.1 Correr los tags `l10n_ve_accountant_rate_tz` y `l10n_ve_sale` tras el upgrade de los módulos
- [ ] 3.2 Navegador, después de las 8 pm con usuario en `America/Caracas`: crear y confirmar una orden de venta, crear una factura y registrar un pago → toman la tasa del día local
- [ ] 3.3 Regresión: antes de las 8 pm el comportamiento no cambia
