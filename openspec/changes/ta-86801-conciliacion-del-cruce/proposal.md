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
- No se crean asientos nuevos.
- Opción de la compañía "Publicar los cruces del PdV" (`pos_post_cross_moves`,
  marcada por defecto) en Ajustes, Configuración del PdV. Marcada, el cruce se
  publica al crearse, como hasta ahora. Desmarcada, queda en borrador y sin la
  línea del diario real; cuando contabilidad lo publica se crea esa línea y se
  concilia (`account.move._post_pos_cross`). El cruce guarda su sesión y su
  método (`pos_cross_session_id`, `pos_cross_payment_method_id`) y la línea su
  cruce (`pos_cross_real_move_id`): publicarlo otra vez no la duplica.

## Impact

- `l10n_ve_pos/models/pos_session.py`, `account_move.py`,
  `account_bank_statement_line.py`, `res_company.py`, `res_config_settings.py`
- `l10n_ve_pos/views/res_config_settings.xml`, `i18n/es_VE.po`
- Campos nuevos: hay que actualizar el módulo.
- `l10n_ve_pos/tests/test_pos_session_cross_account_move.py`
- Cuentas transitorias sin "Permitir conciliación": todo sigue como antes.
- Con el módulo `accountant` (enterprise), la línea de extracto que crea un
  usuario sin permisos contables (el cajero, con Facturación o Gerente de PdV)
  queda sin revisar (`checked`): su transitoria se concilia y el dinero llega a
  la cuenta principal del diario real, pero el tablero la muestra pendiente
  hasta que contabilidad la marca revisada. Decisión del 2026-11-27: se deja
  así, es el control estándar de Odoo y el paso en que contabilidad confirma
  que el dinero llegó (pasa igual con la línea que crea el core para la
  entrada/salida). No se marca revisada desde el código.
