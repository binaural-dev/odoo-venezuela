## Why

Tarea 86801 ("Mejoras al POS - Puntuales", punto 1), punto abierto de la guía:
la línea de extracto que el cruce crea en el diario real quedaba sin conciliar.
Contabilidad tenía que conciliarla a mano, una por cruce, contra la línea del
cruce en la transitoria del diario real; hasta entonces la transitoria acumulaba
partidas abiertas sesión tras sesión (por ejemplo, la sesión `Caja 1/00087` del
staging posconsultoria).

## What Changes

- `_reconcile_statement_line_with_cross(statement_line, cross_line)`: concilia la
  línea abierta de la línea de extracto en la cuenta de la línea del cruce contra
  esa línea. No hace nada, y la deja para conciliarla a mano, si la cuenta no es
  conciliable, la línea del cruce ya está conciliada, la línea de extracto no
  tiene exactamente una línea abierta en esa cuenta o no suman cero en la moneda
  de la compañía (un cruce a otra tasa que la del día de la línea de extracto).
- `_create_cross_real_statement_lines` concilia cada línea de extracto que crea
  contra su línea del cruce, uno a uno, en el orden en que las crea. Aplica a
  todo cruce que deja línea en el diario real: entradas/salidas de los cajones y
  ventas del efectivo sin cajón.
- `binaural_pos_close` usa el mismo método para conciliar la línea de la
  entrada/salida en el diario del cajón contra su cruce.
- No se crean asientos nuevos ni cambia cuándo llega el dinero al diario real.

## Impact

- `l10n_ve_pos/models/pos_session.py`
- `l10n_ve_pos/tests/test_pos_session_cross_account_move.py`
- Cuentas transitorias sin "Permitir conciliación": todo sigue como antes.
- Con el módulo `accountant` (enterprise), Odoo marca como no revisada
  (`checked`) la línea de extracto que crea un usuario sin permisos contables y
  la muestra como no conciliada mientras no se revise, aunque su transitoria lo
  esté. No se cambia aquí: queda para la prueba con un cajero.
