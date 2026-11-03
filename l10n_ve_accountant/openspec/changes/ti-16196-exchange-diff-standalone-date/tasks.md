## 1. Implementación

- [x] 1.1 `_prepare_reconciliation_single_partial`: si el core no armó asiento, la fecha pasa por `journal.accounting_date` sobre `max(debit, credit)`.
- [x] 1.1b La resolución de la fecha vive en `_get_alt_exchange_date` (testeable por rama).
- [x] 1.2 Bump de versión (`19.0.1.0.42`).

## 2. Tests

- [x] 2.1 `tests/test_exchange_diff_date_vs_native.py` (con `Form`): factura USD, alterno ON == OFF; standalone fechado como el nativo (pagando cada día y re-conciliando).
- [x] 2.1b Lado cliente (cuenta por cobrar) y ramas de `_get_alt_exchange_date`: fecha del core, regla del diario, diario sin configurar y fecha de bloqueo.
- [x] 2.2 `tests/test_foreign_exchange_diff.py`: mixin compartido y tasas de fin de mes en `_ensure_usd_rate`.

## 3. Verificación manual

- [ ] 3.1 Informar al consultor: R1 no es obligatorio y el comportamiento observado es el del core (ver proposal).
