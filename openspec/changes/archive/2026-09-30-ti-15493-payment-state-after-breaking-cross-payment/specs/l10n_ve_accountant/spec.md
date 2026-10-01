## ADDED Requirements

### Requirement: `payment_state` se recalcula al romper una conciliación, incluso para pagos con cuenta de pago propia

Cuando se elimina un `account.partial.reconcile` (desconciliar, cancelar un pago, o un flujo que reemplaza una conciliación existente por otra), el sistema DEBE (MUST) marcar `payment_state` de las facturas/pagos tocados como pendiente de recalcular, sin importar si el pago involucrado tiene su propia `payment_account_id` configurada en la línea de método de pago -- el caso NORMAL de cualquier diario bancario real, que el núcleo (`_get_to_update_payments`) excluye de su propio refresco de `payment.state` al desconciliar, dejando `payment_state` de la factura sin recomputar aunque `amount_residual` ya esté correcto.

Esta marca DEBE (MUST) ser perezosa (`env.add_to_compute`), NUNCA un recompute inmediato dentro del mismo `unlink()`: un recompute inmediato captura el estado de la conciliación a mitad de camino en flujos que borran una pieza y crean su reemplazo en la MISMA operación (p. ej. el cruce de anticipo de `l10n_ve_igtf`), resolviendo `payment_state` a `'partial'` incluso cuando la factura termina totalmente pagada por el reemplazo.

#### Scenario: Desconciliar 3 pagos reales, uno por uno, devuelve la factura a "no pagada"

- **GIVEN** una factura pagada en 3 pagos separados vía el wizard de registro de pago, cada uno con su propia `payment_account_id` en el diario bancario
- **WHEN** se desconcilian los 3 pagos, uno por uno, vía el widget de la factura
- **THEN** `payment_state` de la factura queda en `'not_paid'`, sin quedar atascado en `'paid'`

#### Scenario: Un cruce que reemplaza una conciliación existente no captura un estado intermedio

- **GIVEN** un flujo (p. ej. el cruce de anticipo) que borra una conciliación existente y crea su reemplazo en la misma operación
- **WHEN** la conciliación de reemplazo deja la factura totalmente pagada
- **THEN** `payment_state` termina en `'paid'`, no en `'partial'` por haber sido calculado antes de que el reemplazo existiera
