## 1. l10n_ve_accountant — alterno coherente en asientos de extracto

- [x] 1.1 `models/account_move_line.py`: `_compute_foreign_debit_credit` depende de `move_id.line_ids.amount_currency` y `move_id.line_ids.currency_id`
- [x] 1.2 `models/account_bank_statement_line.py`: `edit_reconcile_line` sincroniza `balance` y `amount_currency` con la tasa de la fecha del asiento
- [x] 1.3 `__manifest__.py`: dependencia `account_accountant` y versión 19.0.1.0.51
- [x] 1.5 `models/account_bank_statement_line.py`: `create` completa `amount` desde `amount_currency` a la tasa de la fecha cuando llega en 0 con moneda extranjera
- [x] 1.4 `tests/test_foreign_unbalanced_16410.py`: 12 pruebas (control, Form del asiento, balance forzado, solo balance, solo monto, moneda de la compañía, diálogo con Form real, conciliación sin editar, línea de extracto solo en moneda extranjera, monto explícito, Form de la línea, línea en moneda de la compañía)

## 2. Verificación

- [x] 2.1 Sin la corrección fallan las pruebas del asiento descuadrado en $
- [x] 2.2 Suite completa de `l10n_ve_accountant` en base limpia con `account_accountant` y `l10n_ve`: 507 pruebas, 0 fallos
- [x] 2.3 Probado por la interfaz en staging (diario Banco): USD + monto 1.700 da 1.571.400,78 Bs y remanente 128.599,22 Bs en la cuenta puente; forzar el balance a 1.700.000 deja USD 1.839,12; ambos cuadran en Bs y en $
- [x] 2.6 Probado en staging (diario `Bank-$` sin moneda): una línea con solo USD 10,82 queda en 10.001,5 Bs; con un pago de 10,82 USD la conciliación no genera diferencial cambiario y el asiento cuadra en Bs y en $
- [ ] 2.4 Confirmar por qué flujo se crearon los ~700 pagos `O-` de producción (el cambio del widget solo cubre la edición manual)
- [ ] 2.5 Correr `SCRIPT_CORRECCION_16410.py` en MAXCAM con `DRY_RUN = True` y revisar el listado antes de aplicarlo
