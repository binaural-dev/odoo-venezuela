## Why

En el PdV con doble moneda (Bs. base + USD alterna), cuando el cajero cobra un monto **superior al total** y no indica un método de pago para el vuelto, el asiento contable del vuelto queda con las columnas de moneda alterna (`foreign_debit` / `foreign_credit`) en **0,00**, aunque en la moneda base cuadra. La causa: el núcleo de Odoo crea la línea de pago del cambio en el servidor (`pos.order._process_payment_lines`, con `is_change=True`) sin `foreign_amount` ni `foreign_rate`. Tanto los asientos de pago de factura (`pos.payment._create_payment_moves`) como los asientos de cierre de sesión (`pos.session`) construyen el alterno a partir de `payment.foreign_amount`, de modo que un valor ausente propaga el descuadre: al conciliar contra la factura, en USD se aplica el pago completo sin restar el vuelto. (Ticket #15126.)

## What Changes

- `l10n_ve_pos`: sobrescribir `pos.order._process_payment_lines` para poblar, al momento de crearse, el `foreign_amount` y el `foreign_rate` de la línea del vuelto (`is_change`) a partir de la tasa foránea de la orden (`foreign_currency_rate`), reutilizando un nuevo helper `pos.order._amount_to_foreign(amount)` que espeja la conversión `localToForeign` del frontend.
- `l10n_ve_pos`: red de seguridad en `pos.payment._create_payment_moves`: si una línea de pago llega con `foreign_amount == 0` pero con `amount`, derivar el alterno de la tasa de la orden antes de escribir `foreign_debit`/`foreign_credit`, para no volver a poner el alterno en cero por ninguna vía.

## Impact

- Specs afectadas: `l10n_ve_pos` (nueva requirement "Monto en moneda alterna del vuelto en los asientos").
- Código: `l10n_ve_pos/models/pos_order.py` (helper + override de `_process_payment_lines`), `l10n_ve_pos/models/pos_payment.py` (fallback en `_create_payment_moves`). Bump de manifest 1.12 → 1.13.
- Solo afecta el cálculo del alterno de líneas de pago cuyo alterno estaba ausente (el vuelto). No cambia importes en Bs., ni la partida doble base, ni la lógica de facturación/sincronización. El signo del `foreign_amount` sigue al del `amount` (vuelto negativo); los consumidores ya usan `abs()`.
