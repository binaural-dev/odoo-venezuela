# Fix: la tasa de los asientos del PdV fuera de la convención (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H18 (al analizar H7, 06-oct-2026). Cada asiento guarda
`foreign_inverse_rate` = multiplicador compañía → alterna, con el que
`l10n_ve_accountant` calcula el alterno de las líneas, y `foreign_rate` = su
inverso (`l10n_ve_rate`, `res.currency.rate.compute_rate`; con la compañía en
Bs, 803,34 / 0,001245; con la compañía en USD, 0,001245 / 803,34). La caja (`pos.config`) guarda la misma pareja y el motor de
conversión del PdV (`_get_pos_conversion_rate` y su espejo JS) elige una u otra
según el sentido. La factura y el asiento de pago del PdV, en cambio, llevaban
el multiplicador en los dos campos (0,001245 / 0,001245); en posv19 eran los
únicos: 332 asientos, 5 facturas y 7 pagos de otros orígenes siguen la
convención.

Ningún cálculo usa `foreign_rate` del asiento (las líneas, la MF, la
conciliación, las retenciones y el resumen de impuestos usan
`foreign_inverse_rate` o el `foreign_price` de cada línea), pero sí lo leen:

- la factura digital (`l10n_ve_invoice_digital` y `binaural_unidigital`), como
  Bs por divisa: con la tasa pequeña manda `tipoCambio` 0.0012 y convierte los
  montos dividiendo entre 0,001245; en la forma de pago lee el `foreign_rate`
  del asiento de pago del PdV;
- la tasa informativa de las retenciones y del informe de facturas;
- el chatter: cada factura del PdV registraba "la tasa cambió de 803,34 a
  0,001245".

## What Changes

- **`models/pos_config.py`**: `_get_move_foreign_rate_vals(multiplicador)`,
  junto al motor de conversión, devuelve
  `{foreign_inverse_rate: m, foreign_rate: 1 / m, manually_set_rate: True}`, o
  nada sin tasa (el asiento toma la de su fecha en vez de un 0 fijo). Arma el
  inverso del multiplicador congelado de la orden, no lee la tasa de hoy de la
  caja.
- **`models/pos_order.py`** (`_prepare_invoice_vals`) y
  **`models/pos_payment.py`** (`_create_payment_moves`): usan ese método.
- **`l10n_ve_pos_igtf/models/pos_payment.py`**: su `_create_payment_moves`
  (reimplementado sin `super()`) también.
- En integra-addons, `binaural_pos_multicurrency` (`_prepare_invoice_vals`) lo
  usa con su tasa compañía → alterna (PR #2896).

## Non-goals

- `compute_inverse_rate` de `l10n_ve_rate` (el onchange de la tasa manual)
  pone las dos tasas iguales cuando la alterna no es USD, y el docstring de
  `pos.config._get_pos_conversion_rate` dice lo mismo para la compañía en USD;
  `compute_rate` y el motor de conversión de la caja usan la pareja inversa.
  Aquí se sigue a `compute_rate` (lo que tienen los demás asientos y la caja);
  esa incoherencia de `l10n_ve_rate` queda fuera.

- Migrar las facturas y asientos de pago ya publicados: la cabecera es
  informativa, el alterno no cambia y lo ya enviado a la factura digital no se
  reenvía. Una NC de una factura vieja hereda su tasa (`reversed_entry_id`).

## Impact

- Las facturas y los asientos de pago del PdV muestran 803,34 y la factura
  digital recibe la tasa en Bs por divisa. Simulado en posv19 (odoo shell,
  rollback) con tres órdenes reales: los apuntes y los totales en Bs y en $ son
  idénticos con las dos convenciones.
- El asistente de pago de Contabilidad no cambia: recalcula la tasa por fecha.
- Tests: `tests/test_pos_payment_foreign_rate.py` (motor, factura, asiento de
  pago), `l10n_ve_pos_igtf/tests/test_pos_igtf_payment_move_rate.py` y la
  batería e2e de `binaural_pos_multicurrency` (`test_move_rate_convention` en
  las tres cajas).
