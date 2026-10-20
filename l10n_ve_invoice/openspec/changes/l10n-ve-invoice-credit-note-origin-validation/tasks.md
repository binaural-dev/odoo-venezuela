## 1. Validación en `l10n_ve_invoice`

- [x] 1.1 Agregar `_check_refund_against_origin` (`@api.constrains("invoice_line_ids")`) en `models/account_move.py`: bloquea producto ajeno a la factura origen y monto acreditado por producto mayor al facturado, respetando `l10n_ve_skip_refund_origin_validation`. Verificado leyendo el diff.
- [x] 1.1.1 Corrección post-review (code review interno): el chequeo de monto ahora suma también las demás Notas de Crédito no canceladas contra el mismo origen (`sibling_refunds`), no solo la que se está guardando -- cierra el hueco donde dos NC parciales, cada una individualmente dentro del tope, podían juntas exceder el monto facturado.
- [x] 1.1.2 Corrección post-review (agente independiente `binaural-fn-programador:code-reviewer`): una línea de NC sin `product_id` (línea de descripción manual) ya no se ignora silenciosamente -- ahora se rechaza explícitamente con `ValidationError`, porque antes permitía acreditar cualquier monto sin pasar por ninguno de los dos chequeos (ni de producto ni de monto). Nueva traducción agregada.
- [x] 1.2 Agregar `models/account_move_line.py` con `_check_refund_line_against_origin` (`@api.constrains("product_id", "price_unit", "quantity", "discount")`) que reusa el método anterior sobre `move_id`. Verificado leyendo el diff.
- [x] 1.3 Registrar el nuevo archivo en `models/__init__.py`.
- [x] 1.4 Bump de manifest `19.0.1.0.10` -> `19.0.1.0.11`.
- [x] 1.5 Agregar traducciones ES-VE de los dos mensajes de error nuevos en `i18n/es_VE.po`. Verificado con `msgfmt --check`.

## 2. Coordinación con módulos que crean NC automáticas

- [x] 2.1 Confirmar que `l10n_ve_exchange_difference` ya pasa `l10n_ve_skip_refund_origin_validation=True` en los dos puntos donde crea/postea su NC de diferencial (`account_move_line.py:697,745`, `account_move.py:475`).
- [x] 2.1.1 Corrección post-review (agente independiente): esos dos puntos crean la NC de diferencial **sin** `reversed_entry_id` (se vincula después, en un `write({'reversed_entry_id': ...})` posterior a postear y conciliar, `account_move_line.py:814`), así que el flag del `create()` era redundante y ese `write` tardío -- el único punto real donde se setea el vínculo -- no llevaba el bypass. Hoy no falla porque el constrains no se dispara al escribir `reversed_entry_id`, pero queda a un cambio de alcance del constrains de romperse silenciosamente. Se agregó el flag también en ese `write` como defensa en profundidad.
- [x] 2.2 Agregar el mismo flag en `l10n_ve_donation/models/account_move.py` (`_reverse_moves`), que crea NC con un producto de donación dedicado. Bump de manifest `19.0.2.0.2` -> `19.0.2.0.3`.
- [x] 2.3 Revisar `integra-addons` (repo de cliente, `binaural_19/src/integra-addons`) por creación programática de NC. Ningún módulo crea `account.move` con `move_type` refund vía `create()`; `binaural_commissions`, `binaural_stock_landed_foreign_costs` y `binaural_pos_commissions` solo leen `move_type`/`reversed_entry_id`, y `set_reversed()` en `binaural_commissions` vincula un move ya existente sin crear una NC nueva. No requieren el bypass.

## 3. Tests

- [x] 3.1 `l10n_ve_invoice/tests/test_refund_origin_validation.py`: NC válida (con aserción de monto/producto, no solo "no lanzó"), producto ajeno bloqueado, línea sin producto bloqueada, monto excedido bloqueado, NC de compra (`in_refund`) también validada, NC sin `reversed_entry_id` documentada como gap intencional, bypass permite producto ajeno, dos NC parciales que juntas exceden el origen quedan bloqueadas, `write()` de línea a producto ajeno bloqueado, `write()` de línea que sube el monto sobre el tope bloqueado. Registrado en `tests/__init__.py`.
- [x] 3.1.1 Renombrado `test_line_write_after_post_is_also_validated` -> `test_line_write_to_foreign_product_is_blocked` (agente independiente señaló que el nombre prometía cobertura de posteo y de monto que el test no daba; la NC nunca llega a postear en ese test, solo prueba el camino de producto ajeno). Se agregó un test separado para el camino de monto vía `write()`.
- [x] 3.2 `l10n_ve_donation/tests/test_donation_credit_note_regression.py` (módulo sin carpeta `tests/` previa, creada): confirma que la reversión automática de una factura de donación crea la NC con el producto de donación (corrección), y que la misma NC sin el bypass es rechazada por la validación de `l10n_ve_invoice` (reproduce la regresión que motivó el fix).

## 5. Pendientes documentados (no resueltos en este cambio, señalados por el agente independiente)

- [ ] 5.1 El bypass `l10n_ve_skip_refund_origin_validation` es una clave de contexto sin gate de permiso -- cualquier usuario con acceso a crear facturas puede forjarla vía RPC. Migrar a un campo persistido con `groups=` restringido resolvería esto y a la vez el punto 2.1.1 de forma más robusta.
- [ ] 5.2 Sin conversión de moneda: si la NC queda en una moneda distinta a la de la factura origen, `price_subtotal` se compara crudo entre monedas. Requiere `currency_id._convert(...)` antes de comparar.
- [ ] 5.3 Condición de carrera: dos transacciones concurrentes creando NC contra el mismo origen no se ven entre sí (`sibling_refunds` sin lock), así que en teoría ambas podrían pasar y exceder el tope igual. Requeriría `SELECT ... FOR UPDATE` sobre el origen.
- [ ] 5.4 Performance: `_check_refund_line_against_origin` reejecuta el chequeo completo (incluyendo el `search` de `sibling_refunds`) por cada `write()` de línea -- O(n²) en escenarios de importación masiva. Aceptable para uso interactivo.

## 4. Verificación manual

- [ ] 4.1 Actualizar `l10n_ve_invoice`, `l10n_ve_donation` y `l10n_ve_exchange_difference` en un ambiente Odoo 19 real y confirmar que actualizan sin error.
- [ ] 4.2 Crear factura, NC parcial válida, NC con producto distinto (debe fallar) y NC que exceda el monto (debe fallar).
- [ ] 4.3 Confirmar que revertir una factura de donación sigue funcionando (regresión que motivó el punto 2.2).
- [ ] 4.4 Confirmar que la conciliación con diferencial cambiario (NC de pérdida) sigue posteando sin el error nuevo.
