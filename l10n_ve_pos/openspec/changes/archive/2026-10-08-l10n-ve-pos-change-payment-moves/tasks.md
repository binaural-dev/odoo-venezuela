# Tasks

## 1. Tests

- [x] 1.1 `tests/test_pos_change_payment_moves.py`: vuelto en otro método,
      en el mismo método, vuelto con el cobro de su método, dos pagos del
      mismo monto, método dividido, vuelto en varios métodos y conciliación
      de la factura
- [x] 1.2 Batería e2e de `binaural_pos_multicurrency`: `assertKnownBug` de H12
      → aserciones (`test_sales_receivable_reconciled` en las cajas VES y USD,
      `test_receivable_zero_foreign` en la EUR)

## 2. Corrección

- [x] 2.1 `pos_payment.py`: `_create_payment_moves_by_method` (sin fundir en
      métodos divididos ni con vueltos de varios métodos, code review)
- [x] 2.2 `pos_payment.py`: `_create_payment_moves` por asiento
      (`pos_payment_ids`), alterno = suma con signo

## 3. Verificación

- [x] 3.1 Rojo antes del fix y verde después: `./odoo test -i posv19 -m l10n_ve_pos -d <bd> --tags "/l10n_ve_pos:TestPosChangePaymentMoves"` sin el fix 5/6 en rojo (antes del test de varios vueltos) (asiento fundido entre métodos 1 != 2, tasa sin fijar, vuelto con el cobro de otro método, alternos cruzados 2118 / 2117, método dividido 1 != 2; la conciliación de la factura pasa igual, es salvaguarda) y 7/7 con él. Capa A de integra (`TestE2EAltBox`/`TestE2ECompanyBox.test_sales_receivable_reconciled`, `TestE2EThirdBox.test_receivable_zero_foreign`): 3/3 en rojo antes (±5.374,34, ±1.606,68, 0,01 en alterno) y 3/3 en verde después
- [x] 3.2 Suites sin regresiones (BD nuevas, 07-oct): `l10n_ve_pos` 107/107; capa A de `binaural_pos_multicurrency` 65/69 (los 3 tours por el dbfilter y `test_refund_keeps_original_rate` por `l10n_ve_stock`, previos); tours con `--db-filter` 3/3; hoot `@l10n_ve_pos/` 87/104 (los 17 de `pos_order_line_discount`, previos) y `@binaural_pos_multicurrency/` 8/8; `-u l10n_ve_pos` en posv19
- [x] 3.3 Navegador (posv19, 07-oct). Antes (06-oct): Caja VES, sesión 479, 70 $ en Efectivo USD con vuelto de 1.606,68 en Efectivo Bs → un asiento POSS/2026/0149 de 54.627,12 sin tasa fijada y, al cerrar, ±3.213,36 abiertos en 1122003; Caja EUR, sesión 477, 60.000 Bs con vuelto de 5,71 € → POSE/2026/0013 a 68,01 en alterno. Después: Caja VES, sesión 481 (orden 000006) → POSS/2026/0151 (56.233,80 / 70,00) y POSS/2026/0152 (vuelto 1.606,68 / 2,00), tasa fijada, INV/2026/0107 pagada; al cerrar (POSS/2026/0153) toda la 1122003 conciliada. Caja EUR, sesión 477 (orden 000003) → POSE/2026/0014 (60.000 / 74,68) y POSE/2026/0015 (5.368,83 / 6,68): neto 68,00, INVE/2026/0006 pagada
