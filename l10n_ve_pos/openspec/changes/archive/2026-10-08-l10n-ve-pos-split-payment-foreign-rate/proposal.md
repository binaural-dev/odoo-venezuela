# Fix: el pago split de un banco que no está en la moneda alterna descuadra en alterno al cambiar la tasa (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H15. Reproducido el 07-oct-2026 en posv19, en el navegador
(Caja USD Prueba/00243: 10.000 Bs por el banco Bs con `split_transactions` a
803,34, tasa a 850 antes del cierre → BUT/2026/0003 con la liquidez en 11,76 y
la cuenta del cliente en 12,45) y en `odoo shell` sin guardar en las cajas VES,
USD y EUR.

El core de Odoo 19 crea los `account.payment` de los métodos con
`split_transactions` en lote: `_create_bank_payment_moves` llama a
`_create_split_account_payments`, y `_create_split_account_payment` solo delega
en él. El override de `l10n_ve_pos` estaba en el método singular, que el cierre
no llama nunca. Quedaban sin aplicar:

- el alterno de las dos líneas del pago (`_create_bank_payment_moves` solo fija
  la línea por cobrar con el `foreign_amount` del cobro; la de liquidez la
  calcula `l10n_ve_accountant` a la tasa de la fecha del asiento, el cierre);
- la tasa del pago (se queda con la de su fecha);
- el contexto `from_pos` que leen `l10n_ve_igtf` y `l10n_ve_invoice`.

Pasa con un banco split cuyo diario no está en la moneda alterna (Bs, una
tercera moneda o un diario transitorio sin moneda) cuando la tasa de la fecha
del cierre no es la que usó la caja: cambio a mitad de sesión, cierre otro día o
caja sin recargar la tasa. Con un diario en la moneda alterna el alterno sale
de `amount_currency` y cuadra; el efectivo split y los métodos combinados ya
cuadraban.

## What Changes

- **`models/pos_session.py`**: el override pasa de `_create_split_account_payment`
  a `_create_split_account_payments` (el que usa el cierre). Por cada pago:
  - el `account.payment` y su asiento llevan la tasa del cobro
    (`pos.payment.foreign_rate`, con `pos.config._get_move_foreign_rate_vals`, la
    misma convención que los demás asientos de pago del PdV, `manually_set_rate`
    incluido) en vez de la de su fecha;
  - todas las líneas de su asiento llevan `abs(foreign_amount)` del cobro, con
    `not_foreign_recalculate`;
  - el core se llama con `from_pos=True`, que el cierre nunca pasaba (el override
    singular no se ejecutaba); en el PdV no cambia nada contable (`igtf_amount`
    del pago solo lo llena el asistente de pago).
- El override singular se quita: el del core delega en el lote.

## Non-goals

- `_create_combine_account_payment` no cambia (su override sí se ejecuta y el
  pago cuadra; sigue con la tasa de `pos.config`).
- Sesiones ya cerradas: sin migración.

## Impact

- Tests: `tests/test_pos_split_payment_foreign_rate.py` (liquidez con el alterno
  cobrado, tasa del pago y del asiento, lote con dos pagos a tasas distintas, pago
  saliente, el singular pasa por el lote) y la
  aserción de tasa de `test_pos_session_accounting_move_creation.py` (tasa del
  cobro en vez de la de `pos.config`). En `binaural_pos_multicurrency`,
  `test_rate_change_split_no_phantom_exchange` pasa de `assertKnownBug` a
  aserción.

- Orden de merge: este PR (odoo-venezuela #1414) antes que integra #2896, cuya
  capa A ya afirma H15 corregido.
