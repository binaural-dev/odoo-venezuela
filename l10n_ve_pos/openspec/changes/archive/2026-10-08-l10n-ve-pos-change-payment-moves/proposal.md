# Fix: el vuelto en otro método deja la 1122003 sin conciliar y el alterno sin fijar (l10n_ve_pos)

## Why

Tarea 83148, hallazgo H12 (prueba integral del 01-oct-2026, reproducido en
posv19 el 06-oct). El core (`point_of_sale`, `pos.payment._create_payment_moves`)
funde el vuelto en efectivo con el primer cobro en efectivo de la orden en un
solo asiento de pago por el neto, **sea del método que sea**. El vuelto lo crea
el servidor siempre en el primer método de efectivo de la caja
(`pos.order._process_payment_lines`), así que basta cobrar con el segundo
efectivo: en la Caja VES, 70 $ en Efectivo USD por una venta de 54.627,12 Bs
dan un vuelto de 1.606,68 en Efectivo Bs y un único asiento de 54.627,12.

Dos efectos:

1. **1122003 sin conciliar.** Al cerrar la sesión el core concilia la cuenta por
   cobrar del PdV por método (`_accumulate_amounts` y
   `_reconcile_account_move_lines`). La línea del asiento fundido entra en los
   dos grupos: el del cobro la concilia contra el bruto y le deja un residuo, y
   el del vuelto se queda sin contrapartida. Quedan dos partidas que netean
   cero sin conciliar (±1.606,68 en la caja VES, ±5.374,34 en la USD,
   ±5.368,83 en la EUR), y el residuo cae donde lo deje el orden del plan de
   conciliación, a veces sobre el pago de otra orden.
2. **Alterno sin fijar.** `l10n_ve_pos` buscaba el asiento de cada pago por
   monto (`abs(payment.amount) == move.amount_total`). El neto no coincide con
   ningún pago: el asiento no recibía la tasa ni el alterno y se recalculaba a
   la tasa de la fecha (Caja EUR: 1122003 a 68,01 en vez de 74,68 − 6,68 =
   68,00). Pasa también con el vuelto del mismo método (30.000 − 3.320,79), y
   dos pagos del mismo monto emparejaban cada uno con el asiento del otro.

## What Changes

- **`models/pos_payment.py`**, `_create_payment_moves_by_method` (nuevo, lo
  llama `_create_payment_moves`):
  - Si hay un cobro en efectivo del mismo método que el vuelto, se le pasa
    primero al core, que funde el vuelto con el primer cobro en efectivo del
    recordset.
  - Si no lo hay, el método es dividido (`split_transactions`, que el cierre
    concilia por pago) o hay vueltos de varios métodos, el core crea los
    asientos de los cobros y el de cada vuelto por separado (el asiento de un
    vuelto suelto es el que ya hace cuando se cobra por banco).
- **`_create_payment_moves`** recorre los asientos, no los pagos: los pagos de
  cada asiento son `move.pos_payment_ids`; la tasa es la del cobro (no la del
  vuelto) y el alterno, la suma con signo de sus `foreign_amount` (con el
  respaldo `_amount_to_foreign` del #15090 para un vuelto sin foráneo).

## Non-goals

- La agrupación por método del cierre del core no se toca: con un método por
  asiento ya concilia.
- `l10n_ve_pos_igtf` reimplementa `_create_payment_moves` sin `super()` con un
  asiento por pago (vuelto incluido): no funde y no tiene H12.
- Las sesiones ya cerradas conservan sus pares abiertos (netean cero; se
  concilian a mano). Decisión del usuario (06-oct): sin migración.

## Impact

- Una orden con vuelto en otro método de efectivo tiene un asiento de pago más
  (el del vuelto). La factura concilia igual: el core toma el débito al cliente
  del vuelto como línea del pago negativo
  (`_get_receivable_lines_for_invoice_reconciliation`).
- `binaural_pos_multicurrency` ajusta el monto en Bs por asiento con
  `pos_payment_ids`: sin cambios.
- Tests: `tests/test_pos_change_payment_moves.py` (asientos, método dividido y
  conciliación de la factura con el vuelto en su asiento) y la batería e2e de
  `binaural_pos_multicurrency` (`test_sales_receivable_reconciled` en las cajas
  VES y USD, `test_receivable_zero_foreign` en la EUR), que cierra las sesiones
  y comprueba la 1122003 conciliada.
