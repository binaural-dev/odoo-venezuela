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

5. **El asiento de cruce de anticipo se podía deshacer por sus botones propios.**
   "Pasar a borrador" o "Cancelar" sobre el cruce lo sacaban de su pago origen por
   fuera de los caminos que lo gestionan, y un cruce ya cancelado y desligado del pago
   podía volver a publicarse sin pago origen y duplicar su efecto contable.

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

- El cruce de anticipo (`is_advance_move`, marca que se escribe al crearlo y NO se borra
  al cancelarlo, a diferencia de `origin_payment_advanced_payment_id`) solo cambia de estado
  por los caminos que lo gestionan: desconciliar desde la factura y pasar a borrador o
  cancelar el pago origen. `button_draft` y `button_cancel` fallan con `UserError` salvo con
  el contexto `move_action_cancel_advance_payment`, que fijan esos caminos (wizard,
  `cancel_advance_payment_transaction`, `remove_igtf_from_account_move` y
  `_unreconcile_and_cancel_advance`). `_post` exige pago origen (la reversión de un cruce
  queda exenta).
- `remove_igtf_from_account_move` registra en el log el error que antes se tragaba en
  silencio al pasar a borrador o cancelar.
- Pago origen: `action_cancel` y `action_draft` cancelan y desligan los cruces que quedaron
  en borrador ligados al pago (`advanced_move_ids` solo trae los publicados). No es
  retroactivo: solo actúa cuando se cancela o pasa a borrador ese pago.

### Decisión funcional: el widget valora a la fecha de la factura; la conciliación manual no cambia

El widget valora un pago en moneda de la compañía anterior a una factura en divisa con la
tasa de la FECHA DE LA FACTURA (`max(invoice_date, line.date)`), y el cruce aplica ese monto.
Con tasas que suben (la realidad venezolana: el Bs pierde valor entre el pago y la factura) eso
puede dejar la factura PARCIALMENTE ABIERTA aunque el pago, el día que se hizo, la cubría.
Se decidió mantenerlo así. La conciliación manual desde apuntes sigue con la valoración
nativa de Odoo (tasa de la fecha del pago): es diseño existente del módulo y queda fuera de
alcance, por lo que el mismo pago puede dar resultados distintos según el camino.

Ejemplo, con tasas de enero (01-01) 36 Bs/$ y de agosto (01-08) 40 Bs/$ y una factura de $100
del 01-08 (4.000 Bs), con un pago en Bs del 01-01 (cubierto por los tests `test_rising_rates_*` de
`l10n_ve_exchange_difference/tests/test_exchange_note_foreign_residual.py`, widget y conciliación manual):

| Pago (01-01) | Widget (valora a 40, fecha de la factura) | Manual (valora a 36, fecha del pago) |
|---|---|---|
| 3.600 Bs | muestra y aplica $90; la factura queda parcial, debe $10 (400 Bs); sin notas | aplica $100; factura pagada; NC de 400 Bs fechada 01-01 |
| 4.000 Bs | muestra y aplica $100; el pago queda consumido; sin notas | aplica $100; al pago le quedan 400 Bs sin aplicar; NC de 400 Bs |

Con tasas que bajan ocurre lo contrario: el sobrante del pago queda como crédito del cliente
en lugar de saldo pendiente en la factura (pago de 4.000 Bs del 01-01 a 40 y factura de $100
del 01-08 a 36: el widget aplica $100 = 3.600 Bs y quedan 400 Bs de crédito; el manual consume
el pago completo con una ND de 400 Bs).

## Fuera de alcance
- La valoración de la conciliación manual desde apuntes (nativa de Odoo, a la fecha del
  pago): no se modifica en este cambio.
- Otras suposiciones de línea única, anteriores a este cambio, en el flujo de
  anticipos (`l10n_ve_igtf` y `l10n_ve_igtf_note_debit`: `factura_line.amount_residual`,
  `receivable_payable_line.id`, `lines_to_match...[:1]`). Limitación conocida, sin ticket:
  - **Bug reproducido** (no causado por este cambio): con `igtf_note_debit_mode = debit_note`, una
    factura con 2 o más cuotas por cobrar, un cliente al que le aplica IGTF y un pago YA
    registrado en un diario IGTF, cruzarlo desde el widget lanza
    `ValueError: Expected singleton: account.move.line(...)` (las líneas son las cuotas) en
    `l10n_ve_igtf_note_debit/models/account_move.py:js_assign_outstanding_line`, que filtra
    las líneas por cobrar no conciliadas y las trata como un solo registro
    (`receivable_payable_line.account_id`); el resto de la función (`receivable_payable_line.id`,
    `lines_to_match`) hace la misma suposición, así que no se arregla en una línea.
  - **Por qué no ocurre en el uso actual:** exige todas las condiciones a la vez (varias cuotas, modo
    `debit_note`, cliente con IGTF, diario IGTF y un pago previo cruzado desde el widget). Registrar el
    pago desde el asistente de la factura es otro camino y funciona con varias cuotas
    (`test_invoice_with_two_installments_computes_bi_igtf`). No se ha reportado en uso.
  - **Criterio funcional:** ese cruce no es un flujo esperado para facturas a cuotas con IGTF.
  - **Si algún día se vuelve un flujo esperado** hay que decidir antes qué cuota recibe el pago y cómo
    se reparte el IGTF entre las cuotas; hoy no hay una regla de negocio definida para eso.
- Cruces de anticipo huérfanos que ya están publicados (sin pago origen: pago borrado por SQL o por
  una integración, o datos anteriores a este cambio): no hay migración. Solo se cancelan cuando se
  desconcilian desde la factura. Antes de desplegar, listarlos con una consulta sobre `account_move`
  (`is_advance_move`, `origin_payment_advanced_payment_id IS NULL`, publicado, sin `reversed_entry_id`,
  con línea en las cuentas de IGTF de la compañía). Cancelar un cruce implica desconciliar todas sus
  líneas, no solo el parcial pedido (igual que un cruce con pago origen).
- La interacción con el flujo de notas de diferencial cambiario está en el
  change `exchange-note-foreign-residual-and-widget-rate` de
  `l10n_ve_exchange_difference`.

## Riesgos y compatibilidad
- **Modo `debit_note` con diario IGTF:** `l10n_ve_igtf_note_debit.js_assign_outstanding_line` arma su propio
  parcial y NO pasa por `l10n_ve_widget_rates`; allí lo aplicado es lo que ese flujo calcula, no necesariamente
  lo mostrado. "Cualquier combinación de monedas" aplica al cruce estándar del widget.
- **Módulo antiguo `binaural_advance_payment_igtf`** (`integra-addons`): está deprecado y no se instala (confirmado
  por el equipo). Se menciona porque crea cruces de anticipo con `origin_payment_advanced_payment_id` posiblemente
  vacío, que las guardas de este cambio no dejarían publicar; al no instalarse, no tiene efecto.
- **Filas de diferencial en los consumidores de `invoice_payments_widget`:** `l10n_ve_iot_mf`,
  `l10n_ve_account_mf`, `l10n_ve_invoice` (fechas de pago), `l10n_ve_payment_extension` y
  `l10n_ve_invoice_digital` recorren las filas sin mirar `is_exchange`, así que las notas (también las del
  lado del pago, que ahora se ven) llegan como una fila de pago más. Preexistente para las notas del lado de
  la factura y para el diferencial nativo. Fuera del alcance de este change (ver `l10n_ve_exchange_difference`).
- **El widget puede dejar una factura en divisa parcialmente abierta** cuando el pago en Bs es
  anterior y la tasa subió (ver la decisión funcional y el ejemplo arriba). Es el costo de que
  lo mostrado sea lo aplicado; quien necesite la valoración a la fecha del pago debe conciliar
  manualmente.
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
