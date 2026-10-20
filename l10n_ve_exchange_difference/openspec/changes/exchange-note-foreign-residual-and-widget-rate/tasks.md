## 1. Implementación

- [x] 1.1 Monto en divisa en 0 en el parcial de cierre de la nota (`_l10n_ve_neutralize_foreign_amount_of_note_partial`, contexto `l10n_ve_exchange_closing_note`).
- [x] 1.2 La línea de la nota no ofrece residual en divisa al cerrarse (cierre con un único parcial exacto).
- [x] 1.3 Una nota por cuota de la factura: campo `l10n_ve_exchange_line_id`, guarda por (factura, pago, cuota) y reversión por parcial.
- [x] 1.4 Widget de pagos: la nota se devuelve como fila de diferencial (`is_exchange`) en moneda de la compañía.
- [x] 1.4b Widget de pagos: también se ven las notas que cierran contra la línea del PAGO (el core las encuentra vía `exchange_move_id`, que las notas no usan), una fila por nota y sin duplicar.
- [x] 1.5 La guarda de duplicados de `_create_exchange_difference_note` solo da por existente la nota que cierra contra la misma línea (un parcial puede dejar diferencial en la factura y en el pago: una nota por línea, como el nativo; sin campos nuevos).
- [x] 1.6 Neutralización del parcial acotada a parciales con una línea de nota, y `_is_exchange_note_line` sin `ensure_one()` para líneas sin asiento.
- [x] 1.6b Bump de versión de `l10n_ve_exchange_difference`.
- [x] 1.6c `l10n_ve_exchange_invoice_id` con índice `btree_not_null`: `_get_exchange_note_partials_against_counterparts` lo busca en cada cálculo del widget de una factura con parciales, también en compañías sin el flujo ND/NC.
- [x] 1.7 Lo de `l10n_ve_igtf` (widget y `compute_bi_igtf`) se movió a su propio change `outstanding-widget-applies-shown-amount`.

## 2. Tests

- [x] 2.1 `tests/common.py`: fixture compartido sin tests (los tests que heredaban de `TestExchangeNoteReversal` pasan a usarlo).
- [x] 2.2 `tests/test_exchange_note_foreign_residual.py`: la nota no reduce el residual en divisa (lado factura y lado pago), matriz de fechas x montos, cierre exacto con un parcial con tasa más favorable, una nota por cuota (residual de ambos lados) y reversión por parcial y total, fila del widget (datos), y widget + notas (VEF->USD, USD->VEF con nota, EUR, sobrepago USD sobre factura VEF con nota en ambas líneas), y notas del lado del pago visibles en el widget (una nota, dos cuotas, y desaparición al desconciliar).

- [x] 2.3 Tasas crecientes (36 -> 40): `test_rising_rates_*` (widget y conciliación manual, pagos de 3.600 y 4.000 Bs) y `test_rate_rise_at_collection_emits_a_debit_note_that_the_payment_settles_with_the_invoice` (ND ligada a la factura, el pago extingue ambas CxC, reversión al desconciliar).
- [x] 2.4 Tests de la neutralización acotada (`test_closing_note_context_does_not_touch_partials_without_a_note_line`) y de `_is_exchange_note_line` sin asiento.
- [x] 2.5 `tests/test_exchange_note_field_indexes.py`: los campos de enlace de las notas están indexados, y los índices existen en PostgreSQL.

## 3. Verificación manual (fuera del alcance de la implementación: se hace en la instancia de pruebas)

- [ ] 3.1 Factura en USD con pago parcial en USD a otra tasa: el "por pagar" en USD no cambia por la nota de diferencial.
- [ ] 3.3 Con `l10n_ve_exchange_use_nd_nc` activo: factura con dos cuotas pagada a otra tasa -> una nota por cuota; desconciliar el pago las revierte todas.
- [ ] 3.4 Con `l10n_ve_exchange_use_nd_nc` activo: factura en Bs pagada con USD desde el widget -> se aplica lo mostrado y la diferencia sale como nota (decisión funcional).
