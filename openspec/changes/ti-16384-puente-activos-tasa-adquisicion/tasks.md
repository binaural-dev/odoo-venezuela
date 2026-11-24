## 1. l10n_ve_accountant_asset — tasa efectiva en las cuotas

- [x] 1.1 `account.asset._get_acquisition_rate_values()`: tasa propia del activo (`foreign_rate` > 0, inversa derivada si falta); si no, última tasa de la tabla en `acquisition_date` (`use_last_rate`); `UserError` sin fecha de adquisición (guarda defensiva) o sin ninguna tasa en esa fecha ni antes
- [x] 1.2 `_prepare_move_for_asset_depreciation`: cuotas de depreciación con `manually_set_rate=True` y la tasa efectiva
- [x] 1.3 `account.move.line._get_non_invoice_foreign_value`: USD = balance / `foreign_rate`, siguiendo reversos
- [x] 1.4 `compute_depreciation_board`: escribe la tasa en el activo solo si no tiene tasa propia, protege cuotas publicadas, corrige solo cuotas nuevas y no escribe si no hay cambios
- [x] 1.5 Cuotas con su fecha real y `auto_post='at_date'` nativo (sin modo `custom`)
- [x] 1.6 Manifiesto 19.0.1.0.2 (sin `auto_install`, depende de `l10n_ve_accountant` y `account_asset`) y `i18n/es_VE.po`

## 2. Migración

- [x] 2.1 `pre-10-remove_custom_auto_post.py`: cuotas de activo en borrador `custom` -> `at_date` con `date = auto_post_custom_date` (también `account_move_line.date`); otros documentos `custom` -> `no` con warning en el log; borrado de las vistas `view_move_form_auto_post_custom` y `view_account_asset_form_publish_date`; idempotente si no existe la columna `auto_post_custom_date`

## 3. Tests (`l10n_ve_accountant_asset/tests/`)

- [x] 3.1 `test_depreciation_manual_rate.py`: cuota con la tasa efectiva en borrador y tras el cron, con y sin factura de compra, adquisición en fin de semana, sin tasa previa bloquea el plan, reverso devuelve el USD original, monto grande sin tasa inversa truncada, asiento no de activo con tasa manual conserva la tasa de la tabla
- [x] 3.2 `test_acquisition_rate.py`: tasa propia gana a la de la tabla, tasa propia en 0 usa la tabla, tasa terca de la factura corregida a la de la tabla sin tasa propia, `binaural_account_asset` dentro y fuera de la cadena del MRO, cuotas publicadas intactas al recalcular y al modificar (omitido con `binaural_account_asset` real), sin escrituras si la tasa ya es correcta, moneda alterna VEF en compañía USD, orden de módulos
- [x] 3.3 `test_effective_rate.py`: tasa propia sin tasa en la tabla, tasa propia sin inversa, tasa propia en 0 con fin de semana, la tasa de la tabla se escribe en el activo solo sin tasa propia, falta de fecha de adquisición, sin tasa en la fecha ni antes (mensaje con activo, fecha y moneda), recalcular con tasa propia no escribe el activo ni las cuotas publicadas
- [x] 3.4 `test_depreciation_future.py`: cuotas futuras `at_date` con fecha real, el cron publica solo la de su fecha, recalcular no duplica borradores, pausar tras cuotas publicadas, modificar con cuotas publicadas (omitido con `binaural_account_asset` real)

## 4. Verificación

- [ ] 4.1 Correr los tests del addon tras el upgrade (`-u l10n_ve_accountant_asset`) junto con `l10n_ve_rate` y `l10n_ve_accountant`
- [ ] 4.2 Validación de Contabilidad del criterio de tasa (propia del activo; si no, fecha de adquisición)
- [ ] 4.3 Correr la migración contra una base real de staging que haya tenido el modo `custom` y revisar el log de documentos pasados a `auto_post='no'`
- [ ] 4.4 Navegador con `binaural_account_asset` instalado: crear activo, validar, recalcular el plan y comprobar que las cuotas publicadas conservan tasa y USD
- [ ] 4.5 Push de la rama y revisión del PR
- [ ] 4.6 Archivar este cambio (`openspec archive`) al cerrar el ticket (lo hace el líder)
