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
- La venta en efectivo se cruza como la salida que la lleva al diario real
  (`_get_sales_cross_sign`): acredita la transitoria del diario del método, que
  la salida de efectivo nativa deja en el debe, y debita la del `cross_journal`.
  Antes iba al revés (ticket 15219): cargaba dos veces esa transitoria y, con el
  cruce publicado y su línea de extracto, sacaba el dinero del diario real.
- El cruce y su línea de extracto se crean en `sudo`: los crea el cierre o la
  entrada/salida del cajero, sin permisos contables (como el cierre nativo).
- La línea de extracto no lleva un socio de otra compañía (`check_company`),
  igual que la cabecera del cruce.

## Impact

- `l10n_ve_pos/models/pos_session.py`, tests de `test_pos_session_cross_account_move.py`,
  `test_pos_tender_currency.py` (signos de la venta en efectivo), `i18n/es_VE.po`
  ("Sales"; sale "PoS Payment Method Adjustment", la etiqueta es la `ref`).
- Los cruces de banco (`use_suspense=False`) también se publican; no generan
  línea de extracto (su pata real va a la cuenta de las líneas de pago).
- `binaural_pos_close` y `binaural_pos_multicurrency` (integra-addons) usan el
  gancho, el signo y el formato de la `ref`: van en el MISMO despliegue que este
  módulo. Solo odoo-venezuela volvería a cruzar las ventas de los cajones (ya
  publicadas); solo integra-addons rompería el cierre de las cajas en otra moneda.
- Configuración necesaria: transitoria distinta por diario y "Permitir
  conciliación" en las dos.
- Fuera de alcance: el punto 2 de la tarea (redondeo en los asientos de salida).
- Rama sobre la de la tarea 86066 (moneda de cobro, PR #1569 abierto): el cruce
  de un método en moneda de cobro también se publica y crea su línea de extracto
  en la moneda de su diario real (EUR). Se mergea después de #1569.
- No toca los borradores de cruce acumulados en las bases (los de ventas de los
  cajones se cancelan, no se publican).
