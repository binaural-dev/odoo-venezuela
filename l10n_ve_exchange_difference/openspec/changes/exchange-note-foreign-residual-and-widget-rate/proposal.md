# Fix: la nota de diferencial no descuenta divisa, cierra exacta, una por cuota y se ve como diferencial

## Why

Tres comportamientos en cruces de facturas/pagos cuyas monedas no coinciden
(moneda de compañía = VEF):

1. **La ND/NC de diferencial descontaba USD del residual de la factura.**
   Ejemplo real: factura $450, pagado $100, nota de diferencial de 8.079,42 Bs
   (≈ $9,19) -> "por pagar" $340,81 en vez de $350,00. Una diferencia
   cambiaria solo ajusta el balance en moneda de la compañía; el asiento
   nativo de diferencial lo logra porque sus líneas están en la MISMA moneda
   foránea que la línea que cierra, con `amount_currency = 0`, y el motor de
   conciliación del core (`_prepare_reconciliation_single_partial`,
   `exchange_line_mode`) solo reduce el balance en ese caso. Nuestra nota es
   un documento real en VEF, así que ese modo no aplica: el motor convertía
   el importe de la nota a la divisa y lo restaba del residual en divisa.

2. **Con varias cuotas solo se emitía una nota por par factura/pago.** La guarda
   `existing_note` (por factura y pago) dejaba sin nota la diferencia de las
   demás cuotas y el pago quedaba con Bs colgados. El asiento nativo emite un
   diferencial por cada línea con residual.

3. **Las notas se veían en el widget de pagos como un pago/reverso**, por el
   monto en divisa del parcial (ver 1), en lugar de como un diferencial.

El cruce desde el widget de créditos pendientes que aplica lo mostrado (y su
interacción con estas notas) se documenta en el change
`outstanding-widget-applies-shown-amount` de `l10n_ve_igtf`.

## What Changes

### `l10n_ve_exchange_difference`
- `account.move.line._prepare_reconciliation_single_partial`: cuando el cierre
  lo hace `_create_exchange_difference_note` (contexto
  `l10n_ve_exchange_closing_note`), el monto en divisa de la línea cerrada
  (factura o pago, si no está en moneda de compañía) queda en 0 EN EL PARCIAL,
  antes de crearse. No se corrige después de creado: el residual almacenado
  (`amount_residual_currency`) solo se recalcula cuando cambia el conjunto de
  parciales, no sus montos.
- `account.move.line._prepare_move_line_residual_amounts`: en ese mismo
  contexto la línea de la nota NO ofrece residual en la divisa de la
  contraparte, así el motor concilia en moneda de la compañía y la nota cierra
  SIEMPRE con un único parcial por su monto exacto. Verificado: sin esto el
  motor la cierra con parciales sucesivos que convergen por redondeo (4 en el
  escenario de prueba), porque el monto en Bs cerrado sale de `min()` entre la
  tasa de la fecha de la nota y la contable de la línea que cierra.
- Una nota POR CUOTA de la factura (como el asiento de diferencial nativo, que
  emite uno por cada línea con residual y se revierte con el parcial que lo
  originó), sin importar de qué lado -- factura o pago -- quede el residual:
  - nuevo campo `account.move.l10n_ve_exchange_line_id`: la línea por cobrar de
    la factura (la cuota) cuyo cruce originó la nota (sin migración: las notas
    anteriores quedan sin línea);
  - la guarda de duplicados de `_create_exchange_difference_note` pasa a ser por
    (factura, pago, cuota), y las notas sin línea siguen cubriendo el par;
  - `_l10n_ve_exchange_note_for_partial` devuelve las notas de la cuota de la
    factura que cruza el parcial (más las anteriores sin línea), así romper un
    parcial revierte solo la nota de su cuota.
- Widget de pagos de la factura: las ND/NC de diferencial se devuelven como filas de
  diferencial (`is_exchange`), igual que el asiento nativo, en moneda de la compañía y con el
  monto en Bs del parcial (`_get_all_reconciled_invoice_partials`). El parcial de la nota lleva
  monto en divisa 0 del lado del documento: antes la fila mostraba un pago/reverso engañoso.
  También se ven las notas que cierran contra la línea del PAGO, que no es parcial de la
  factura y el core no encuentra (el nativo las ve vía `exchange_move_id`, que las notas no
  usan para no duplicar la reversión): ocurre cuando el pago vale más Bs que la factura (tasa
  mayor), el caso habitual con tasas que suben y el pago posterior a la factura. Las filas se
  agregan en `_get_exchange_note_partials_against_counterparts`, con parciales reales (el
  reporte impreso solo lista filas con `is_exchange == 0`, así que no cambia el PDF).
- Tests: fixture compartido `tests/common.py` (`ExchangeNoteCommon`, sin tests
  propios) en lugar de heredar de `TestExchangeNoteReversal`, que obligaba a
  repetir ~80 tests en cada subclase.

- La neutralización del parcial de la nota (`_l10n_ve_neutralize_foreign_amount_of_note_partial`) se aplica
  solo si una de las dos líneas del parcial es de una nota (`_is_exchange_note_line()`), no solo por el
  contexto `l10n_ve_exchange_closing_note`, que sigue vivo en conciliaciones anidadas. Es preventivo: sin
  esa condición, una conciliación anidada con el contexto puesto y sin línea de nota deja en 0 los montos
  en divisa, el residual nunca baja y el motor entra en bucle hasta agotar memoria (reproducido forzando el
  contexto). NO se pudo reproducir en un flujo real: con impuestos de exigibilidad al pago (CABA) y una
  nota de diferencial, el asiento de caja se concilia FUERA del cierre de la nota (sin el contexto).
- `_is_exchange_note_line` devuelve `False` (no revienta) para una línea sin asiento.

### Interacción con el cruce desde el widget (`l10n_ve_igtf`)
El cruce desde el widget aplica el monto mostrado (change
`outstanding-widget-applies-shown-amount`). **Decisión funcional: ese monto es el
que se cruza y, si resulta un diferencial cambiario, se genera como cualquier
diferencial nativo de Odoo, que con el flujo de ND/NC activo es una nota.** Por
ejemplo, una factura de 4.000 Bs con un pago anterior de 80 USD: el widget
muestra y aplica 2.880 Bs (80 x 36) y la diferencia con el balance del pago
(3.200 Bs) sale como una ND de 320 Bs; el cruce nativo habría aplicado 3.200 Bs
sin nota.

Con tasas que suben (pago en Bs anterior a la factura en divisa) el widget valora a la fecha de la
factura y puede dejar la factura parcialmente abierta, mientras que la conciliación manual conserva
la valoración nativa (fecha del pago) y emite la NC por la diferencia. Es una decisión funcional ya
tomada, con ejemplos y valores en el change `outstanding-widget-applies-shown-amount` de `l10n_ve_igtf`.

## Fuera de alcance
- El vínculo `debit_origin_id`/`reversed_entry_id` de la nota con su factura se
  conserva: otros módulos (libros de compra y venta, validaciones de fecha de
  NC/ND respecto a su origen, IGTF) dependen de él, y las notas SHALL seguir
  apareciendo en los libros.
- `l10n_ve_invoice_digital` NO se modifica: si una nota de diferencial se
  digitaliza o no es una decisión administrativa del cliente, no del módulo.
- Sin migración: son correcciones hacia adelante; las notas ya emitidas no se
  tocan (documentos publicados, posiblemente de períodos cerrados).

## Riesgos y compatibilidad
- **Notas antiguas sin línea (`l10n_ve_exchange_line_id` vacío) y la guarda de duplicados:** una nota emitida
  antes de este cambio que cierra contra la línea de un pago se reconoce como existente para cualquier cuota.
  Si luego el resto de ese mismo pago se cruza con otra cuota, su diferencial no emite nota y queda sin
  documento. Transitorio (solo notas anteriores a la actualización) y ya ocurría antes con `limit=1`.
- **NC/ND por céntimos desde el widget:** al cruzar un pago en otra moneda que cubre de sobra una factura en
  Bs, el redondeo a centavos de la tasa del widget puede dejar un diferencial de céntimos del lado de la
  factura (ej.: 0,04 Bs) que, con el flujo ND/NC activo, sale como una NC fiscal con correlativo, además de la
  ND del lado del pago. Cubierto por `test_widget_usd_overpayment_on_vef_invoice_settles_both_sides`.
  **Decisión funcional: se acepta** (no se aplica tolerancia de redondeo ni umbral).
- **Notas contra el pago (ND de ganancia):** se mantienen como estaban. Se evaluó que solo el diferencial del
  lado de la factura emitiera nota y el del pago fuera al asiento nativo, y se descartó: queda como está hasta
  que contabilidad confirme el criterio fiscal (si la ganancia cambiaria requiere documento al cliente).
- Acoplado a Odoo 19.0-20260710: `_prepare_reconciliation_single_partial`,
  `_prepare_move_line_residual_amounts` y la estructura de `partial_values` son
  internos del core.
- **Con `l10n_ve_exchange_use_nd_nc` activo, respetar el monto del widget puede
  emitir ND/NC FISCALES con correlativo que antes no salían** (ver el ejemplo
  arriba: cualquier pago en USD más viejo que una factura en Bs, o el remanente
  de un pago registrado con `l10n_ve_conversion_date` cruzado contra otra
  factura). Consumen correlativos fiscales: lo funcional ya decidió que el monto
  del widget manda y el diferencial se genera como en el flujo nativo.
- Las notas se ligan a la cuota de la factura: al romper un parcial se revierten
  solo las de esa cuota (y las anteriores sin línea, por par factura/pago). Si un
  mismo pago cruza varias cuotas, cada una conserva su propia nota aunque todas
  dejen su residual del lado del pago.
- **Posible cambio en el PDF de la factura (por lectura del core, no probado):** con
  `is_exchange=True` el reporte nativo (`account/views/report_invoice.xml`,
  `payment_vals['is_exchange'] == 0`) no imprimiría las notas como líneas "Paid on", igual
  que el diferencial nativo. La máquina fiscal (`l10n_ve_iot_mf`, `l10n_ve_account_mf`) sigue leyendo
  esas filas y respeta `currency_id`: ahora recibe los Bs exactos de la nota.

