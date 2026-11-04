# Tasks

## 1. Tests

- [x] 1.1 `tests/test_pos_split_payment_foreign_rate.py`: liquidez con el alterno cobrado, tasa del pago y del asiento, lote con dos pagos a tasas distintas, pago saliente y el singular del core por el lote
- [x] 1.2 `test_pos_session_accounting_move_creation.py`: el `account.payment` lleva la tasa del cobro, no la de `pos.config`
- [x] 1.3 `binaural_pos_multicurrency` (integra, PR #2896): `test_rate_change_split_no_phantom_exchange` de `assertKnownBug` a aserción

## 2. Corrección

- [x] 2.1 `pos_session.py`: override en `_create_split_account_payments` (tasa del cobro en el pago y en el asiento, alterno en todas las líneas, `from_pos`); fuera el singular
- [x] 2.2 Code review (07-oct, aprobar con cambios menores): test del lote con dos pagos, `rate_vals` también en el asiento (paridad con H18), comentario del test y precisiones de la propuesta

## 3. Verificación

- [x] 3.1 Rojo antes del fix y verde después (07-oct, posv19, BD nuevas): `TestPosSplitPaymentForeignRate` sin el fix 3/4 en rojo (liquidez 2.320 = 58 × 40 en vez de 2.117 = 58 × 36,5; tasa del pago 40 en vez de 36,5; el singular pasa igual, salvaguarda) y `TestPosSessionAccountingMoveCreation` con la tasa de `pos.config`; verde con él. Simulación con rollback de 13 variantes en posv19 (cajas VES, USD y EUR; banco Bs, € y transitorio; con y sin cambio de tasa): todas cuadran en alterno y el resto de invariantes no cambia
- [x] 3.2 Suites sin regresiones (07-oct, BD nuevas): `l10n_ve_pos` 111/112 tras el code review (el fallo, `TestPosDataLoading.test_lst_price_converted_once_when_currency_differs`, también sin el fix: entorno del checkout de posv19); capa A de `binaural_pos_multicurrency` 68/72 con H15 en aserción (los 3 tours por el dbfilter y `test_refund_keeps_original_rate`, previos)
- [x] 3.3 Navegador (posv19 reiniciado, 07-oct). Antes: Caja USD Prueba/00243, orden 265-82-000006 (10.000 Bs por Banco Bs split + 55,55 $ por Banco USD a 803,34, USD a 850 antes del cierre) → BUT/2026/0003 con liquidez 11,76 y 1122001 12,45, pago a 850. Después: Caja USD Prueba/00257, orden 265-82-000007, misma venta → BUT/2026/0004 con 12,45 / 12,45, pago y asiento a 803,34 (`manually_set_rate`); BUU/2026/0006 y POSS1/2026/0042 cuadrados. Split, tasa y sesiones vacías revertidos

## 4. CI del PR (#1414)

- [x] 4.1 Reproducido en local (BD nueva, solo enterprise + esta rama + third-party, `l10n_ve_pos` + `l10n_ve_pos_igtf` como el CI): 3 fallos, los mismos 3 del CI (113 tests allí, 118 aquí con los de H15). No eran de H15:
  - `TestPosChangePaymentMoves.test_change_in_same_cash_method_merged_with_net_foreign` y `test_change_merged_with_the_payment_of_its_method` (H12): con `l10n_ve_pos_igtf` instalado, su `_create_payment_moves` reemplaza al de `l10n_ve_pos` sin `super()` (un asiento por pago), así que los tests no ejercían el código de H12. Ahora llaman a la implementación de `l10n_ve_pos` (`_payment_moves`)
  - `TestPosDataLoading.test_lst_price_converted_once_when_currency_differs` (doble conversión del precio): la tasa del test es de su propia compañía y la carga corría con la compañía principal del entorno (el core convierte con `self.env.company`) → 10,00 sin convertir. Ahora carga con la compañía de la sesión, como el PdV
- [x] 4.2 Tras el arreglo: 118/118
