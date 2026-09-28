## Why

Al desconciliar un pago con IGTF (factura en VEF pagada en USD) y reaplicar el anticipo resultante sobre la misma factura, esta puede quedar con un residuo fantasma en vez de cerrar pagada — confirmado en un caso real (factura VEF del 01/09, pago USD del 23/09): 569.766,95 Bs.F de residuo tras reaplicar, compuesto de dos causas independientes. (Ticket #15367.)

**Causa 1 — tasa incorrecta.** El asiento "CRUCE DE ANTICIPO" que arma `account.move._create_advance_payment_move()` no queda marcado como "un pago real" ante el núcleo (`is_payment()` en `account_move_line.py:_prepare_move_line_residual_amounts`, que solo mira `origin_payment_id`/`statement_line_id`). Al conciliar, el núcleo usa entonces la tasa de la FECHA DE LA FACTURA en vez de la tasa real del cruce, generando un diferencial cambiario ficticio proporcional a la brecha entre esas dos fechas (385.384,95 Bs.F en el caso real).

**Causa 2 — reparto del IGTF.** El guard que debía absorber el IGTF con el sobrante del anticipo (`if (base_amount_applied + igtf_in_invoice_curr) < advance_amount`) nunca disparaba: al reaplicar el anticipo COMPLETO, esa suma da exactamente IGUAL a `advance_amount` (no "menor" por comparación estricta de floats), así que el IGTF se le recortaba a la línea de CxC en vez de tomarse del sobrante — residuo del tamaño del IGTF, incluso sin ninguna brecha de tasa (184.381,45 Bs.F en el caso real).

Adicionalmente, un pago que liquida el TOTAL de una factura VEF en USD dejaba un asiento de "diferencial cambiario" espurio de unos pocos bolívares (puro redondeo de centavos de dólar en dos conversiones sucesivas, no una pérdida/ganancia cambiaria real), porque `_is_same_within_rounding` solo comparaba en la moneda de la compañía.

## What Changes

- `l10n_ve_igtf`: override completo de `account.move.line._prepare_move_line_residual_amounts` (no se puede parchear en aislado: `is_payment`/`get_odoo_rate`/`get_accounting_rate` son funciones locales del núcleo) para que `is_payment()` también reconozca el asiento "CRUCE DE ANTICIPO" (`is_advance_move=True`) como un pago real, sin poblar el campo estándar `origin_payment_id` (evita duplicar esa relación 1:1 sobre dos asientos para el mismo `account.payment`).
- `l10n_ve_igtf`: en `account.move._create_advance_payment_move`, el guard que absorbe el IGTF con el sobrante del anticipo pasa de comparación estricta (`<`) a `currency.compare_amounts(...) <= 0` (tolerancia de redondeo de la moneda en vez de float crudo).
- `l10n_ve_igtf`: en `account.payment._prepare_inbound_move_line_igtf_vals` / `_prepare_outbound_move_line_igtf_vals`, se agrega una segunda comparación en la moneda DEL PAGO (no solo en VEF) antes de forzar el balance al residual exacto de la factura — elimina el diferencial cambiario espurio en pagos completos.
- Bump de manifest `l10n_ve_igtf` 19.0.1.2.17 → 19.0.1.2.18.

## Impact

- Specs afectadas: `l10n_ve_igtf` (nueva requirement "Reaplicación de anticipo con IGTF cierra sin residuo").
- Código: `l10n_ve_igtf/models/account_move.py`, `l10n_ve_igtf/models/account_move_line.py`, `l10n_ve_igtf/models/account_payment.py`.
- Solo afecta el ciclo desconciliar→reaplicar un pago con IGTF y el cierre de pagos completos en moneda distinta a la factura. No cambia el cálculo del IGTF en el pago original, ni la lógica de anticipos sin IGTF.
