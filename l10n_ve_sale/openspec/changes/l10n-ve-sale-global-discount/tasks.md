## 1. Implementación

- [x] 1.1 `l10n_ve_sale`: mixin de documento, asistente, campos de compañía/ajustes, grupos, vistas y `tax_totals`.
- [x] 1.2 `l10n_ve_invoice`: mixin de línea `l10n_ve.discount.line.mixin` y utilidad `spread_amount` compartida.
- [x] 1.3 `l10n_ve_deductible`: reparto compartido y rechazo por descuento global.
- [x] 1.4 Corrección post-review (revisor Binaural): los campos del esquema y de aprobación se protegen contra escritura directa y la clave de contexto se sustituyó por una marca interna del cursor.
- [x] 1.5 Corrección post-review: comparaciones de importes con `currency.is_zero` / `float_compare`.
- [x] 1.6 Bump de manifests (`l10n_ve_sale`, `l10n_ve_invoice`, `l10n_ve_deductible`).

## 2. Tests

- [x] 2.1 `test_discount_schemes.py`, `test_discount_limits.py` (incluye intentos de bypass por RPC) y `test_discount_deductible.py`.

- [x] 2.2 Pruebas del flujo de etapa, bloqueo, notificaciones, alternos de apuntes y botón oculto.
- [x] 2.3 `l10n_ve_invoice/tests/common.py`: tasa del día para las pruebas de `l10n_ve_invoice` (60 errores previos, necesarios para aprobar el PR en la rama vertical).

## 3. Pendientes documentados (otro PR)

- [ ] 3.1 En la factura, "Por aprobar" es un campo (barra de aprobación), no un estado de `account.move`; el bloqueo de campos solo existe en pedidos.
- [ ] 3.2 TFHKA no admite el descuento global sobre el Total (se rechaza antes de enviar).
- [ ] 3.3 Verificar la máquina fiscal (`l10n_ve_account_mf`, `l10n_ve_iot_mf`): usa solo `line.discount`; probar con importe fijo y descuento global.
- [ ] 3.4 `_compute_discount_allocation_needed` copia parte de la lógica nativa: revisar en cada migración de Odoo.
- [ ] 3.5 Dividir en PR por módulo si el equipo lo pide (`l10n_ve_invoice`, `l10n_ve_sale`, deducible, TFHKA).
