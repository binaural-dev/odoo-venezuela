## 1. l10n_ve_rate

- [x] 1.1 `compute_rate`: `datetime` → `context_today`; fecha vacía → «hoy» del usuario

## 2. Llamadores

- [x] 2.1 `l10n_ve_sale`, `l10n_ve_pos`, `l10n_ve_accountant`, `l10n_ve_igtf`, `l10n_ve_payment_extension`, `l10n_ve_suggested_amount`, `l10n_ve_fiscal_lock_days`
- [x] 2.2 `binaural_purchase`, `binaural_payment`, `binaural_foreign_cost`, `binaural_last_cost`, `binaural_appointment`, `binaural_invoice_lots`, `binaural_stock_advance`, `binaural_stock_landed_foreign_costs`, `binaural_mobile_igtf`, `binaural_website_sale`, `payment_megasoft`
- [x] 2.3 Defaults de wizards evaluados al abrir, no al importar

## 3. Tests

- [x] 3.1 Escenario 2026-03-11 00:30 UTC = 2026-03-10 20:30 en Caracas, con tasa solo hasta el día 10 (`l10n_ve_accountant/tests/common_tz_boundary.py`)
- [x] 3.2 Reproducen el error antes de la corrección: `l10n_ve_sale` (3), `binaural_purchase` (2), `l10n_ve_pos` (1), `binaural_payment` (1)
- [x] 3.3 Guarda de regresión que ya pasaba: `l10n_ve_accountant` (6: factura de venta/compra, asiento, pago)
- [x] 3.4 `binaural_foreign_cost/tests/test_stock_move.py`: carga la tasa de hoy que necesita
- [x] 3.5 Se incorporan las pruebas de la PR #1531 (`test_rate_date_user_tz.py`, `test_sale_order_rate_tz.py`): factura sin fecha a las 9 pm toma la tasa del día local y una `invoice_date` explícita no se corrige

## 4. Verificación

- [x] 4.1 1148 pruebas de los módulos tocados: sin fallos nuevos
- [x] 4.2 `binaural_clinics_sale` y `l10n_ve_suggested_amount`: sin fallos nuevos frente a la rama sin cambios
- [ ] 4.3 Sin pruebas o sin poder correrse: `binaural_mobile_igtf`, `binaural_invoice_lots`, `binaural_stock_advance`, `binaural_stock_landed_foreign_costs`, `binaural_appointment`, `binaural_website_sale`, `payment_megasoft` (falta `xmltodict`), `binaural_last_cost` (instalación)
