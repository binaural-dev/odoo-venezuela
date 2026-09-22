## Why

En el PdV con doble moneda, el cierre de sesión genera para cada método de pago en
efectivo en divisa un asiento de cruce (`pos.session._validate_cross_move`) que hoy
lleva el saldo de la **cuenta por defecto del diario del método** hacia la **cuenta
real de liquidez del diario afectado** (`cross_journal`):

```
DEBE   cross_journal → línea de método de pago entrante → payment_account_id
HABER  payment_method.journal_id.default_account_id
```

Ese asiento asume que el cruce es lo único que vacía la cuenta POS del diario del
método. En la operación real no es así: **al cerrar la sesión el cajero registra una
salida de efectivo por el total**, y esa salida ya acredita la cuenta POS y deja el
saldo en la cuenta transitoria del diario del método. El cruce de la venta vuelve a
acreditar la misma cuenta, así que la drena dos veces.

Traza real de una sesión (db `vzla19_lebrum`, sesión `CAJA 1/00033`, método
`1DOLARES C.A.**`, diario 371, cuenta POS `1.7.1.38`, transitoria `1.7.1.06`):

```
942  POS EFECTIVO DOLARES C1 C.A.  DEBE  1.7.1.38     22.095,47   venta (cierre nativo)
914  POS EFECTIVO DOLARES C1 C.A.  HABER 1.7.1.38     22.088,66   salida de efectivo al cierre
                                   DEBE  1.7.1.06     22.088,66
915  CRUCE EFECTIVO DOLAR ***      DEBE  1.7.1.06     22.088,66   cruce de la salida
                                   HABER 1.7.1.06     22.088,66   (misma cuenta → nulo)
945  CRUCE EFECTIVO DOLAR ***      HABER 1.7.1.38     22.095,47   cruce de la VENTA (sobra)
                                   DEBE  1.1.1.05.04  22.095,47
```

Consecuencias medidas en esa base: `1.7.1.38 POS EFECTIVO DOLAR C.A.` acumula saldo
**acreedor** de −329.838,20 (drenada dos veces) y la transitoria `1.7.1.06` queda
**cargada** con +1.244.334,51, sin nada que la compense.

El cierre correcto de la operación es: la cuenta POS del diario del método cierra
contra la salida de efectivo, y el cruce de la venta mueve el importe **entre las
dos cuentas transitorias**, de modo que el dinero de la venta que queda en la
transitoria del diario afectado se compense contra lo que la salida dejó en la
transitoria del diario del método y ambas terminen en cero. La conciliación de los
movimientos del diario del método contra la cuenta del diario principal se hace
antes, por contabilidad.

## What Changes

- `l10n_ve_pos`: en **ventas** (`pos.session._validate_cross_move`), los métodos de
  pago **en efectivo** (`type == "cash"`) con `is_foreign_currency` pasan a cruzar
  transitoria contra transitoria:

  ```
  DEBE   payment_method.journal_id.suspense_account_id      (Cuenta transitoria del diario del método)
  HABER  payment_method.cross_journal.suspense_account_id   (Cuenta transitoria del diario afectado)
  ```

  Para un neto negativo (devoluciones que superan las ventas del método) el asiento
  es el espejo: DEBE la transitoria del diario afectado, HABER la del método.

- Implementación: `_validate_cross_move` pasa `use_suspense=True` para los métodos de
  tipo `cash`, tanto a `_is_cross_move_eligible` como a `_create_cross_move_for`. Esa
  ruta ya existe y ya produce exactamente ese asiento (es la que usa el cash in/out de
  `binaural_pos_close`): `_create_cross_move_for` invierte el constructor de líneas y
  el signo, de modo que para un importe positivo debita la transitoria del diario del
  método y acredita la del `cross_journal`. No hace falta lógica de líneas nueva.

- **No cambia** nada fuera de la venta en efectivo:
  - Métodos de **banco**: siguen cruzando `outstanding_account_id` → cuenta real del
    `cross_journal` (`use_suspense=False`).
  - **Cash in/out** (`binaural_pos_close.try_cash_in_out`): ya iba por
    `use_suspense=True`, sin cambios.
  - **Diferencias de apertura/cierre**
    (`binaural_pos_close._post_foreign_statement_difference`, que llama a
    `_create_cross_move_for` sin `use_suspense`): siguen apuntando a la cuenta real de
    liquidez. Por eso el discriminador va en `_validate_cross_move` y no dentro de
    `_line_vals_move_cross_incoming`/`_outgoing`, que son compartidas.
  - Granularidad (`split_transactions`), montos alternos (`foreign_debit`/
    `foreign_credit`), tasa, `ref`, diario del asiento (`cross_account_journal`) y
    estado borrador: igual que hoy.

## Impact

- Specs afectadas: `l10n_ve_pos` (requirement "Cross moves de compensación para
  métodos en divisa", modificada).
- Código: `l10n_ve_pos/models/pos_session.py` (`_validate_cross_move`). Bump de
  manifest `l10n_ve_pos` 1.17 → 1.18.
- Tests: `l10n_ve_pos/tests/test_pos_session_cross_account_move.py`.
- **Alcance de negocio**: el cambio es incondicional para todo método en efectivo con
  divisa, así que aplica a todos los clientes de la localización, no solo a
  Eléctricos Lebrún. Su premisa es que el efectivo sale de la caja del PdV mediante la
  salida de efectivo del cierre; donde esa práctica no exista, la cuenta POS del
  diario del método quedará con saldo deudor acumulado hasta que se registre.
- **Requisito de configuración**: tanto el diario del método como el `cross_journal`
  deben tener su propia Cuenta transitoria (`suspense_account_id`):
  - Si a alguno le falta, el método se omite en silencio (comportamiento ya existente
    de `_is_cross_move_eligible`) y no se crea cruce.
  - Si ambos apuntan a la **misma** cuenta, el asiento sale con DEBE y HABER en esa
    cuenta (nulo). En `vzla19_lebrum` es el caso del diario 371 `POS EFECTIVO DOLARES
    C1 C.A.` y el 359 `EFECTIVO DOLARES C.A.` (ambos `1.7.1.06`), que ya produce hoy
    asientos nulos en el cash in/out (move 915). Su gemelo de CAJA 2 (diario 372) sí
    tiene la suya (`1.7.1.32`). Es configuración, no código.
- La cuenta de efectivo real en divisa (`1.1.1.05.04` / `1.1.1.05.03`) deja de recibir
  la venta por la vía del cruce.
