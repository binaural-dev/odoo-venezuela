## Why

Al romper la conciliación de un pago cruzado con una factura (desconciliar, cancelar el pago, o un cruce que reemplaza una conciliación existente), la factura vuelve a quedar marcada como "Pagada" en vez de reflejar su estado real. (Ticket #15493.)

**Causa.** `account.move._compute_payment_state` depende de `reconciled_payment_ids.state`, pero el `unlink()` nativo de `account.partial.reconcile` solo refresca el `state` del PAGO para pagos donde `not payment.outstanding_account_id` (`_get_to_update_payments`, núcleo). Un pago cuya línea de método de pago tiene su propia `payment_account_id` configurada -- el caso NORMAL de cualquier diario bancario real, no una configuración rara de cuenta puente -- queda excluido de ese refresco, así que su `state` se queda como estaba (p. ej. `'paid'`) aunque la conciliación que lo pagaba ya no exista. `payment_state` de la factura nunca se recomputa en consecuencia, aunque `amount_residual` y `reconciled_payment_ids` ya estén correctos. Confirmado contra un caso real de producción.

Un problema relacionado, encontrado al corregir el anterior: la corrección existente de `l10n_ve_exchange_difference._compute_payment_state` (que evita que una factura cerrada por ND/NC quede `'reversed'` en vez de `'paid'`) forzaba `'paid'` incondicionalmente en cuanto detectaba una nota propia entre las contrapartes -- incluso cuando, tras desconciliar otra pieza, la nota terminaba siendo la ÚNICA contraparte restante. Ese caso (una sola NC como contraparte) es EXACTAMENTE la definición nativa de `'reversed'` del núcleo, así que forzar `'paid'` ahí sobrescribía un valor correcto y dejaba `payment_state` desactualizado tras desconciliar.

## What Changes

- `l10n_ve_accountant`: nuevo `account.partial.reconcile.unlink()` que marca `payment_state` como "pendiente de recalcular" (perezoso, vía `env.add_to_compute`) en las facturas/pagos tocados por la conciliación borrada -- perezoso y no un recompute inmediato (`_compute_payment_state()` eager) a propósito: un recompute inmediato dentro de `unlink()` captura el estado a mitad de camino en flujos que borran una conciliación y crean su reemplazo en la MISMA operación (el cruce de anticipo), resolviendo mal a `'partial'` incluso cuando la factura termina totalmente pagada.
- `l10n_ve_exchange_difference`: la corrección de `_compute_payment_state` ya no fuerza `'paid'` cuando, al excluir las notas propias, no queda NINGUNA otra contraparte (`remaining_types` vacío) -- ese caso ya lo resuelve bien el núcleo por su cuenta.
- Bump de manifest `l10n_ve_accountant` 19.0.1.0.23 → 19.0.1.0.24, `l10n_ve_exchange_difference` 19.0.0.0.3 → 19.0.0.0.4.

## Impact

- Specs afectadas: `l10n_ve_accountant` (nueva requirement), `l10n_ve_exchange_difference` (refinamiento de requirement existente).
- Código: `l10n_ve_accountant/models/account_partial_reconcile.py`, `l10n_ve_exchange_difference/models/account_move.py`.
- Solo afecta el momento en que se recalcula `payment_state` al romperse una conciliación. No cambia cómo se calcula el monto de la factura, la lógica de conciliación en sí, ni la emisión de ND/NC.
