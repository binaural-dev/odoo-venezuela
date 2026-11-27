## 1. l10n_ve_accountant — alterno coherente en asientos de extracto

- [x] 1.1 `models/account_move_line.py`: `_compute_foreign_debit_credit` depende de `move_id.line_ids.amount_currency` y `move_id.line_ids.currency_id`
- [x] 1.2 `models/account_move_line.py`: las líneas hermanas se leen una vez por asiento durante el recálculo (`_get_foreign_sibling_values`)
- [x] 1.3 `models/account_bank_statement_line.py`: `edit_reconcile_line` sincroniza `balance` y `amount_currency` con la tasa de la fecha del asiento
- [x] 1.4 `models/account_bank_statement_line.py`: `create` completa `amount` desde `amount_currency` a la tasa de la fecha cuando llega en 0 con moneda extranjera
- [x] 1.5 `models/account_bank_statement_line.py`: onchange del formulario (`amount_currency`/moneda extranjera fijan `amount`; `amount`, fecha y diario fijan `amount_currency`)
- [x] 1.6 `__manifest__.py`: dependencia `account_accountant` y versión 19.0.1.0.49
- [x] 1.7 `tests/test_bank_statement_foreign_balance.py`: control, Form del asiento, balance forzado, solo balance, solo monto, moneda de la compañía, diálogo con Form real, conciliación sin editar, línea de extracto solo en moneda extranjera, monto explícito, Form de la línea, onchange en ambos sentidos, cambio de fecha, ajustes manuales que sobreviven al cambio de una línea hermana

## 2. Verificación

- [x] 2.1 Sin la corrección fallan las pruebas del asiento descuadrado en $
- [x] 2.2 Suite completa de `l10n_ve_accountant` en base limpia con `account_accountant` y `l10n_ve`: 515 pruebas, 0 fallos
- [x] 2.3 Probado por la interfaz de un ambiente de pruebas: USD + monto da el balance a la tasa de la fecha con el resto en la cuenta puente; forzar el balance ajusta el monto en moneda; ambos cuadran en Bs y en $
- [x] 2.4 Rendimiento medido con asientos de 200, 600 y 1.200 líneas (ver `design.md`): editar dos líneas de un asiento todo en Bs de 1.201 líneas pasó a 5,50 s con las dependencias nuevas sin optimizar y a 0,11 s con la lectura única por asiento (antes del cambio: 0,06 s)
