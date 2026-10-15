## 1. Validación en `l10n_ve_invoice`

- [x] 1.1 Modificar `_check_refund_against_origin` (`models/account_move.py`): producto tipo `service` ajeno a la factura origen deja de lanzar `ValidationError` y se acumula en `service_exempt_total` en vez de en `current_totals`. Almacenable/Consumible sin cambios.
- [x] 1.2 Corrección post-review (agente independiente `binaural-fn-lider-tecnico:lider-tecnico`): la primera versión dejaba el monto de servicios ajenos sin ningún tope (podía acreditarse un monto ilimitado). Se agregó un chequeo agregado: `service_exempt_total` + productos normales + lo ya acreditado por NC hermanas no puede superar el total facturado en el origen.
- [x] 1.3 Bump de manifest `19.0.1.0.12` -> `19.0.1.0.13`.
- [x] 1.4 Agregar traducción ES-VE del nuevo mensaje de error agregado en `i18n/es_VE.po`.

## 2. Tests

- [x] 2.1 `l10n_ve_invoice/tests/test_refund_origin_validation.py`: servicio ajeno permitido, servicio ajeno bloqueado si excede el total del origen (solo o combinado con otro servicio ajeno), boundary exacto en el total permitido, mezcla producto normal + servicio ajeno (dentro y fuera del total), acumulado entre NC hermanas (una NC con producto normal consume parte del total, una segunda NC con solo servicio ajeno respeta lo que queda).
- [x] 2.1.1 Corrección post-review (agente independiente): los tests que probaban el bloqueo de producto ajeno usaban productos tipo `service` como fixture, por lo que dejaron de fallar por la razón correcta al aplicar este cambio. Se agregó `product_storable` (`type="consu"`) para esos casos y se dejó `service_early_payment`/`product_c` (tipo `service`) para los casos nuevos.
- [x] 2.1.2 Corrección: el fixture inicial usaba el campo `is_storable`, que no existe en el `product.product` de este core (`type` solo admite `consu`/`service`/`combo`). Detectado al correr los tests contra una base de datos nueva instalada desde cero -- en una base ya existente el registro no fallaba porque venía de un esquema previo.

## 3. Verificación

- [x] 3.1 Corridos los 176 tests de `l10n_ve_invoice` (incluye subárbol de `test_refund_origin_validation.py`) contra una base de datos nueva (`test_refund_81674`), instalación limpia desde cero: 0 fallos, 0 errores.
- [x] 3.2 Confirmado que los 3 fallos vistos en una corrida previa contra una base de datos ya existente (`testing`) eran por una vista de `l10n_ve_accountant` (`view_move_form_debit_inherit_l10n_ve`) desactualizada en esa base -- no relacionados a este cambio. Se resolvió con `-u l10n_ve_accountant` en esa base; en la base nueva instalada desde cero no aparece.
