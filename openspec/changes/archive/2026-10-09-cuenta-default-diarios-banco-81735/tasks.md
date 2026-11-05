## 1. `account.journal` -- cuenta obligatoria y propagación

- [x] 1.1 `_check_default_account_id_required_for_bank`: `default_account_id` obligatorio para `type == 'bank'`
- [x] 1.2 `_fill_payment_account_id_from_default`: propaga `default_account_id` a las líneas entrantes/salientes sin cuenta
- [x] 1.3 Llamado desde los overrides de `_compute_inbound/outbound_payment_method_line_ids` (sin redeclarar `@api.depends`, para no reactivar el `Command.clear()` destructivo del compute nativo al editar `default_account_id`) -- bug encontrado por code review (pastor-binaural), con test de regresión
- [x] 1.4 `@api.onchange('default_account_id')` para feedback inmediato en el formulario
- [x] 1.5 Llamado también desde `create()`/`write()` como red de seguridad

## 2. `account.payment.method.line` -- constrains de línea

- [x] 2.1 `_check_payment_account_id_required_for_bank`: cierra el camino de escritura directa sobre la línea, que el constrains del diario no cubre
- [x] 2.2 `create()` rellena `payment_account_id` desde `default_account_id` del diario ANTES de validar -- sin esto, el constrains rompe la creación de cualquier diario banco (compute nativo, `_auto_link_payment_methods`, payment providers)

## 3. `account.payment` -- bloqueo de confirmación

- [x] 3.1 Override de `_get_outstanding_account`: deshabilita el fallback silencioso a `transfer_account_id`/chart template para diarios banco sin cuenta en la línea
- [x] 3.2 Guard en `action_post`: rechaza confirmar con un error explícito si el diario es banco y no hay `outstanding_account_id`

## 4. Migración

- [x] 4.1 `19.0.1.0.28`: rellena `payment_account_id` en diarios banco existentes desde `default_account_id`, loguea los que no tengan ninguno

## 5. Tests

- [x] 5.1 `test_account_journal_bank_account.py`: cobertura de 1-3 (creación con cuenta, línea manual, diario sin cuenta, diarios sin líneas, línea mixta con/sin cuenta, escritura directa, diario de caja exento, pago configurado genera asiento, línea heredada sin cuenta bloqueada)
- [ ] 5.2 Pendiente (señalado por code review): camino con la app completa de Contabilidad instalada (requiere `patch.object` sobre `_get_invoice_in_payment_state`), pago saliente generando asiento, flujo del asistente "Registrar pago"

## 6. Documentación

- [x] 6.1 Spec de `l10n_ve_accountant` actualizada (este change)
- [ ] 6.2 Pendiente, fuera de este change: definir con negocio/Saúl la fuente de `default_account_id` mismo (requisito 1 del ticket) y decidir cómo tratar los pagos de Punto de Venta en el guard de `action_post`
