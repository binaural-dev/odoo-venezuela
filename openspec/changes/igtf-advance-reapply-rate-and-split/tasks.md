## 1. l10n_ve_igtf — tasa del cruce de anticipo

- [x] 1.1 Override de `account.move.line._prepare_move_line_residual_amounts` (copia del núcleo Odoo 19.0 + un cambio: `is_payment()` también reconoce `is_advance_move`)
- [x] 1.2 Advertencia de mantenimiento en el docstring (re-diffear contra el núcleo en cada upgrade de Odoo)

## 2. l10n_ve_igtf — reparto del IGTF al reaplicar

- [x] 2.1 `_create_advance_payment_move`: guard `< advance_amount` → `currency.compare_amounts(...) <= 0`
- [x] 2.2 `_prepare_inbound_move_line_igtf_vals` / `_prepare_outbound_move_line_igtf_vals`: segunda comparación en la moneda del pago antes de forzar el balance al residual exacto

## 3. Manifest y tests

- [x] 3.1 Bump de manifest `l10n_ve_igtf` 19.0.1.2.17 → 19.0.1.2.18
- [x] 3.2 Test de regresión: factura VEF con brecha de fecha, ciclo pagar→desconciliar→reaplicar, cierra 'paid' sin residuo (`test13b`)
- [x] 3.3 Test: pago completo no genera diferencial cambiario espurio (`test13c`)
- [x] 3.4 Casos borde: pago parcial real, subpago real, sobrepago real -- ninguno se confunde con redondeo (`test13d`-`test13f`)
- [x] 3.5 Caso borde: factura con cantidad decimal y precio a 6 decimales (`test13g`)

## 4. Verificación

- [x] 4.1 Sin los fixes, el test de regresión falla con un residuo fantasma (reproducido: 2.636,40 Bs.F en un caso sintético, 569.766,95 Bs.F en el caso real)
- [x] 4.2 Con los fixes, el mismo test pasa limpio
- [x] 4.3 Regresión: las 96 pruebas de `l10n_ve_igtf` (tag `igtf_run`) siguen en verde
- [x] 4.4 Regresión: las pruebas de `l10n_ve_accountant` (real_portion, rounding) siguen en verde
