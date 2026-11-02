## 1. l10n_ve_payment_extension

- [x] 1.1 `account.retention.line`: no crear líneas de IVA con alícuota 0 (onchange de `move_id` y de `aliquot`)
- [x] 1.2 `action_view_retention`: configuración por tipo con vistas explícitas, lista ISLR propia y `context` con `default_type` / `default_type_retention`; tipo desconocido sin acción
- [x] 1.3 Spec: escenarios de diferenciador vacío y de línea de IVA con alícuota 0, y requisito de los botones de retenciones
- [x] 1.4 Traducción es_VE del aviso nuevo

## 2. Tests

- [x] 2.1 `test_retention_consolidated_duplicates.py`: con `Form` y la vista IVA, "Agregar una línea" asigna la alícuota real, una factura sin IVA no genera línea, la alícuota 0 manual se revierte y consolidar B en A sigue bloqueando el duplicado; diferenciador vacío en ISLR y municipal
- [x] 2.2 `test_wizard_payment_batch.py`: comprueba el id de vista real y el `context`; caso de tipo desconocido

## 3. Verificación

- [x] 3.1 BD nueva, imagen `local_odoo_proj:19`: `-u l10n_ve_payment_extension --test-tags /l10n_ve_payment_extension`: 438 tests, 0 fallos
