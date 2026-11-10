## Why

Tarea 86801 ("Mejoras al POS - Puntuales", punto 1). En la prueba de consultoría
(staging posconsultoria, Caja 1, sesiones 00049 y 00050) el cruce del efectivo en
divisa llevó el dinero hasta la transitoria del diario real, pero:

1. Nada lo movía al diario real: su tablero no tenía líneas que conciliar y hubo
   que crearlas a mano, una por cruce.
2. El cruce de las ventas en efectivo movía otra vez un dinero que ya llevaba la
   salida de efectivo del cierre (lo resuelve `binaural_pos_close` con el gancho
   de este cambio).
3. Una línea del diario real solo se concilia contra UN cruce de su transitoria
   ("el asiento de diario siempre debe tener solo una línea transitoria").
4. Todas las líneas del tablero decían "PoS Payment Method Adjustment", sin la
   sesión: se conciliaba contra el cruce de otra sesión.
5. Cada cierre dejaba sus cruces en borrador.

Aunque la prueba fue con euros, aplica a todos los cruces.

## What Changes

- El cruce se publica al crearse (`_create_cross_move`), ya no queda en borrador.
- Cada línea del cruce sobre la transitoria del diario real (`cross_journal`)
  crea en ese diario su línea de extracto, con el mismo monto en la moneda del
  diario, la misma alterna, el mismo socio y la misma etiqueta, sin conciliar:
  se concilia uno a uno contra su cruce desde el tablero. No se crea si esa
  transitoria es también la del diario del método (no se sabe cuál pata es la
  del diario real).
- La `ref` del cruce empieza con la sesión (`Caja 1/00050 · Sales · Efectivo USD`
  o `Caja 1/00050 · <orden> · <pago>`) y es también la etiqueta de sus líneas.
- Gancho `_crosses_sales(payment_method)` (siempre `True` aquí) que
  `_validate_cross_move` consulta para cruzar las ventas de un método.

## Impact

- `l10n_ve_pos/models/pos_session.py`, tests de `test_pos_session_cross_account_move.py`,
  `i18n/es_VE.po` ("Sales").
- Los cruces de banco (`use_suspense=False`) también se publican; no generan
  línea de extracto (su pata real va a la cuenta de las líneas de pago).
- `binaural_pos_close` y `binaural_pos_multicurrency` (integra-addons) usan el
  gancho y el formato de la `ref`: se despliegan después de este módulo.
- Configuración necesaria: transitoria distinta por diario y "Permitir
  conciliación" en las dos.
- Fuera de alcance: el punto 2 de la tarea (redondeo en los asientos de salida).
- Rama sobre la de la tarea 86066 (moneda de cobro, PR #1569 abierto): el cruce
  de un método en moneda de cobro también se publica y crea su línea de extracto
  en la moneda de su diario real (EUR). Se mergea después de #1569.
