## 1. Implementación

- [x] 1.1 Monto en divisa en 0 en el parcial de cierre de la nota (`_l10n_ve_neutralize_foreign_amount_of_note_partial`, contexto `l10n_ve_exchange_closing_note`).
- [x] 1.2 La línea de la nota no ofrece residual en divisa al cerrarse (cierre con un único parcial exacto).
- [x] 1.3 Una nota por cuota de la factura: campo `l10n_ve_exchange_line_id`, guarda por (factura, pago, cuota) y reversión por parcial.
- [x] 1.4 Widget de pagos: la nota se devuelve como fila de diferencial (`is_exchange`) en moneda de la compañía.
- [x] 1.5 La guarda de duplicados de `_create_exchange_difference_note` solo da por existente la nota que cierra contra la misma línea (un parcial puede dejar diferencial en la factura y en el pago: una nota por línea, como el nativo; sin campos nuevos).
- [x] 1.6 Neutralización del parcial acotada a parciales con una línea de nota, y `_is_exchange_note_line` sin `ensure_one()` para líneas sin asiento.
- [x] 1.6b Bump de versión de `l10n_ve_exchange_difference`.
- [x] 1.7 Lo de `l10n_ve_igtf` (widget y `compute_bi_igtf`) se movió a su propio change `outstanding-widget-applies-shown-amount`.

## 2. Tests

- [x] 2.1 `tests/common.py`: fixture compartido sin tests (los tests que heredaban de `TestExchangeNoteReversal` pasan a usarlo).
- [x] 2.2 `tests/test_exchange_note_foreign_residual.py`: la nota no reduce el residual en divisa (lado factura y lado pago), matriz de fechas x montos, cierre exacto con un parcial con tasa más favorable, una nota por cuota (residual de ambos lados) y reversión por parcial y total, fila del widget (datos), y widget + notas (VEF->USD, USD->VEF con nota, EUR, sobrepago USD sobre factura VEF con nota en ambas líneas).

## 3. Verificación manual

- [ ] 3.1 Factura en USD con pago parcial en USD a otra tasa: el "por pagar" en USD no cambia por la nota de diferencial.
- [ ] 3.3 Con `l10n_ve_exchange_use_nd_nc` activo: factura con dos cuotas pagada a otra tasa -> una nota por cuota; desconciliar el pago las revierte todas.
- [ ] 3.4 Con `l10n_ve_exchange_use_nd_nc` activo: factura en Bs pagada con USD desde el widget -> se aplica lo mostrado y la diferencia sale como nota (decisión funcional).
