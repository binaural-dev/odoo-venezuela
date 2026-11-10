# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el defecto (factura de 100 USD a 300, cierre a 330): el
      asiento deja 9,09 USD en CxC y en ganancia cambiaria
- [x] 1.2 Causa: `amount_currency = 0` en las líneas del asistente nativo; la
      rama 5 de `_get_foreign_value` no aplica y cae en
      `_get_non_invoice_foreign_value`
- [x] 1.3 Verificado que la reversión copia el valor alterno (sin residuo
      permanente): el efecto es el USD fantasma entre el cierre y la reversión
- [x] 1.4 Verificado con la fecha de reversión movida y con un pago intermedio

## 2. Fix

- [x] 2.1 Heredar `account.multicurrency.revaluation.wizard` y sobrescribir
      `_get_move_vals` con `not_foreign_recalculate` y alternos en 0
- [x] 2.2 Registrar el archivo en `wizard/__init__.py`
- [x] 2.3 Bump de manifest `19.0.1.0.42` → `19.0.1.0.43`

## 3. Tests

- [x] 3.1 `tests/test_multicurrency_revaluation.py` (7 pruebas): asiento en 0,
      reversión en 0, saldo CxC alterno estable con reversión movida, pago
      intermedio, cuentas por pagar, asiento manual no afectado y vista previa
- [x] 3.2 Comprobado en rojo sin el fix (6 de 7 fallan) y en verde con él
- [x] 3.3 Suite completa de `l10n_ve_accountant`: 407 pruebas, 0 fallos
