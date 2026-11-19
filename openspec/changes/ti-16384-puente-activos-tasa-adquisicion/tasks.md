## 1. l10n_ve_accountant_asset — tasa de adquisición en las cuotas

- [x] 1.1 `account.asset._get_acquisition_rate_values()` con `use_last_rate=True` en la compañía del activo
- [x] 1.2 `_prepare_move_for_asset_depreciation`: cuotas de depreciación con `manually_set_rate=True` y la tasa de adquisición
- [x] 1.3 `account.move.line._get_non_invoice_foreign_value`: USD = balance / `foreign_rate`, siguiendo reversos
- [x] 1.4 `compute_depreciation_board`: fija la tasa en el activo si hay `binaural_account_asset`, protege cuotas publicadas, corrige solo cuotas nuevas y no escribe si no hay cambios
- [x] 1.5 Cuotas con su fecha real y `auto_post='at_date'` nativo (sin modo `custom`)
- [x] 1.6 Manifiesto 19.0.1.0.2 (sin `auto_install`, depende de `l10n_ve_accountant` y `account_asset`)

## 2. Migración

- [x] 2.1 `pre-10-remove_custom_auto_post.py`: cuotas de activo en borrador `custom` -> `at_date` con `date = auto_post_custom_date` (también `account_move_line.date`); otros documentos `custom` -> `no` con warning en el log; borrado de las vistas `view_move_form_auto_post_custom` y `view_account_asset_form_publish_date`; idempotente si no existe la columna `auto_post_custom_date`

## 3. Tests (`l10n_ve_accountant_asset/tests/`)

- [x] 3.1 `test_depreciation_manual_rate.py`: cuota con tasa de adquisición en borrador y tras el cron, con y sin factura de compra, adquisición en fin de semana, sin tasa previa bloquea el plan, reverso devuelve el USD original, monto grande sin tasa inversa truncada, asiento no de activo con tasa manual conserva la tasa de la tabla
- [x] 3.2 `test_acquisition_rate.py`: la tasa de adquisición gana a la de la factura, `binaural_account_asset` dentro y fuera de la cadena del MRO, cuotas publicadas intactas al recalcular y al modificar, sin escrituras si la tasa ya es correcta, moneda alterna VEF en compañía USD, orden de módulos
- [x] 3.3 `test_depreciation_future.py`: cuotas futuras `at_date` con fecha real, el cron publica solo la de su fecha, recalcular no duplica borradores, pausar tras cuotas publicadas, dar de baja sin tasa exacta no falla

## 4. Verificación

- [ ] 4.1 Correr los tests del addon tras el upgrade (`-u l10n_ve_accountant_asset`) junto con `l10n_ve_rate` y `l10n_ve_accountant`
- [ ] 4.2 Validación de Contabilidad de que la tasa de la fecha de adquisición es el criterio correcto
- [ ] 4.3 Correr la migración contra una base real de staging que haya tenido el modo `custom` y revisar el log de documentos pasados a `auto_post='no'`
- [ ] 4.4 Navegador con `binaural_account_asset` instalado: crear activo, validar, recalcular el plan y comprobar que las cuotas publicadas conservan tasa y USD
- [ ] 4.5 Archivar este cambio (`openspec archive`) al cerrar el ticket (lo hace el líder)
