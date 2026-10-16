# Fix: el cruce desde el widget aplica el monto mostrado, y `compute_bi_igtf` admite cuotas

## Why

1. **El cruce desde el widget de créditos pendientes no aplicaba lo que el widget
   mostraba.** El widget (`_compute_payments_widget_to_reconcile_info`) convierte
   el pago a la moneda de la factura con sus propias reglas de fecha
   (`max(invoice_date, line.date)`, `keep_alter_value_vef`), pero
   `js_assign_outstanding_line` del core solo concilia las líneas y el motor
   recalcula la tasa por su cuenta: la fecha del pago si la línea está en moneda
   de la compañía, o solo el balance en Bs si está en una tercera moneda. Si las
   tasas difieren, el crédito aplicado no coincide con el mostrado.
2. **`compute_bi_igtf` reventaba con `Expected singleton`** en facturas con
   varias cuotas por cobrar: buscaba los parciales con `factura_line.id`,
   asumiendo UNA sola línea por cobrar/pagar.
3. **`remove_igtf_from_account_move` pasaba a borrador asientos que no tienen
   línea de IGTF** (asientos en VEF, pagos de diarios sin IGTF, pagos en modo
   `debit_note`, donde el IGTF lo lleva la nota de débito) antes de decidir que
   no había nada que quitar. `button_draft` no es inocuo: desconcilia TODAS las
   líneas del asiento (todos los parciales del pago, no solo el que se rompe) y
   el asiento se volvía a publicar sin cambios; además el llamador
   (`js_remove_outstanding_partial`) creía que ya se había actuado y nunca hacía
   el desconciliado normal del parcial pedido.

4. **Desconciliar un pago con un asiento de cruce de anticipo SIN publicar ligado
   cancelaba el asiento ORIGEN del pago.** `account.payment.advanced_move_ids`
   declaraba su `domain` (solo cruces publicados) como cadena, que en Odoo es solo
   del cliente: el servidor no lo aplica al leer y el campo traía también los cruces
   en borrador o cancelados. Con eso `js_remove_outstanding_partial` entraba a la rama
   que cancela el cruce (`cancel_advance_payment_transaction`) con el asiento del
   propio pago como "cruce", y lo cancelaba. Verificado con un test: ocurría igual
   con el código anterior. El asiento origen nunca debe cancelarse al desconciliar.

## What Changes

- El widget expone `rate` en cada línea: la tasa SIN redondear con la que se
  calculó `amount` (el cociente `monto / residual` heredaría el redondeo del
  monto y perdería precisión con monedas de pocos decimales: JPY 0, KWD 3).
- `js_assign_outstanding_line` fija en contexto `l10n_ve_widget_rates` ->
  `{id de línea: moneda de la contraparte por unidad de la moneda de esa línea}`:
  - pago en VEF, factura en divisa: `{línea del pago: rate}`;
  - pago en divisa, factura en VEF: `{líneas por cobrar/pagar de la factura: 1 / rate}`;
  - pago en una tercera moneda: `{línea del pago: rate}`.
- `_prepare_move_line_residual_amounts` ofrece al motor, para esas líneas, un
  residual en la moneda de la contraparte (`|residual| * rate`, redondeado a esa
  moneda) para que concilie en ella y aplique exactamente lo mostrado.
- `_prepare_reconciliation_single_partial`: para una línea en una tercera
  moneda el core asume que el monto en divisa de AMBAS líneas del parcial está
  en la moneda de conciliación; se reexpresa el de esa línea en su propia
  moneda (proporcional a lo aplicado del valor del widget) y se corrige su
  residual en divisa.
- Se usa el contexto propio y NO `forced_rate_from_register_payment` del core:
  ese lo lee también el cash basis (`account.partial.reconcile`) con otro
  significado (moneda de la factura por moneda de compañía), que daría asientos
  incorrectos con impuestos de exigibilidad al pago.
- Exclusiones: cruces de retenciones (`l10n_ve_payment_extension`, contexto
  `l10n_ve_exchange_is_retention_reconcile`) y la ND de IGTF
  (`l10n_ve_igtf_note_debit_origin`) al saldarse contra el remanente de su pago.
- `compute_bi_igtf` (y la variante de `l10n_ve_igtf_note_debit`) busca los
  parciales contra TODAS las líneas por cobrar/pagar de la factura (`in`).

- `remove_igtf_from_account_move`: si el asiento no tiene línea de IGTF y no es
  un movimiento de reaplicación de anticipos (`origin_payment_advanced_payment_id`),
  devuelve `False` ANTES de tocarlo. El llamador desconcilia entonces solo el
  parcial pedido. Los movimientos de anticipos siguen su camino (se cancelan
  aunque no tengan línea de IGTF).

- `account.payment.advanced_move_ids`: el `domain` pasa de cadena a lista Python, de
  modo que el servidor solo devuelve cruces publicados (`move_type = entry` y estado
  fuera de borrador/cancelado). Con eso un cruce sin publicar no activa la rama de
  cancelación y desconciliar el parcial del propio pago es un desconciliado normal.
  El módulo externo `integra-addons/binaural_advance_payment`, que redefinía el campo
  con otro dominio, está deprecado y no se instala.

## Fuera de alcance
- Otras suposiciones de línea única, anteriores a este cambio, en el flujo de
  anticipos (`l10n_ve_igtf` y `l10n_ve_igtf_note_debit`: `factura_line.amount_residual`,
  `receivable_payable_line.id`, `lines_to_match...[:1]`): ticket aparte.
- La interacción con el flujo de notas de diferencial cambiario está en el
  change `exchange-note-foreign-residual-and-widget-rate` de
  `l10n_ve_exchange_difference`.

## Riesgos y compatibilidad
- Acoplado a Odoo 19.0-20260710 (métodos y estructura de `partial_values` internos).
- Si el pago vale más/menos de lo que el motor aplicaría, la diferencia queda como
  diferencial cambiario, como cualquier diferencial nativo de Odoo (con
  `l10n_ve_exchange_difference` y su flujo de ND/NC activo, como una nota; ver ese
  change).
- Con varias cuotas el pago se reparte en un parcial por cuota y cada uno redondea
  a centavos de la moneda de la factura: el total en Bs puede diferir de lo
  mostrado en unos céntimos.
- `third-party-addons/account_payment_widget_amount`: con `paid_amount` en el
  contexto reescribe `debit/credit_amount_currency` con `_convert` a la fecha de
  la línea, lo que deshace el ajuste de tercera moneda. Preexistente; solo aplica
  donde ese módulo esté instalado.
