## Why

Las cuotas de depreciación de un activo se publican en fechas futuras (cron nativo de `auto_post='at_date'`), a veces en días sin tasa cargada, y su importe en moneda alterna cambiaba según la tasa del día de publicación. Contabilidad requiere que el valor alterno de toda la depreciación se calcule con la tasa de la fecha de adquisición del activo (ticket #16384). Una versión previa del addon resolvía la fecha con un modo propio `auto_post='custom'`, que se elimina: las cuotas vuelven a nacer con su fecha real y el `auto_post` nativo.

## What Changes

- Addon nuevo `l10n_ve_accountant_asset` 19.0.1.0.2 (puente, instalación manual —sin `auto_install`—, depende de `l10n_ve_accountant` y `account_asset`). `binaural_account_asset` NO es dependencia.
- `account.asset._get_acquisition_rate_values()`: tasa de `acquisition_date` con `compute_rate(use_last_rate=True, raise_if_not_found=True)` en la compañía del activo; fin de semana o feriado usan la última tasa anterior; sin ninguna tasa anterior lanza el `UserError` original; sin moneda alterna en la compañía devuelve `{}`.
- `account.move._prepare_move_for_asset_depreciation`: las cuotas `asset_move_type == 'depreciation'` nacen con `manually_set_rate=True` y `foreign_rate`/`foreign_inverse_rate` de la tasa de adquisición, pisando también la tasa de la factura de compra que fija `binaural_account_asset`. Al ser tasa manual, no se recalcula al publicar.
- `account.move.line._get_non_invoice_foreign_value`: el USD de las líneas de una cuota es `(debit - credit) / foreign_rate` de la cuota (siguiendo la cadena de `reversed_entry_id` para los reversos); no usa `foreign_inverse_rate`, que está truncado a 6 decimales en el activo.
- `account.asset.compute_depreciation_board`: fija la tasa de adquisición en el activo si `binaural_account_asset` está instalado (campo `foreign_rate` presente), restaura las cuotas ya publicadas a su tasa previa y corrige solo las cuotas nuevas cuya tasa difiera. Solo escribe si algo cambia.
- Las cuotas futuras nacen con su fecha real y el `auto_post='at_date'` nativo, sin modo propio.
- Migración `migrations/19.0.1.0.2/pre-10-remove_custom_auto_post.py` para bases que tuvieron el modo `auto_post='custom'`.

## Impact

- Specs afectadas: nueva `l10n_ve_accountant_asset` (se AÑADE; no existía). Depende del cambio `ti-16384-ultima-tasa-anterior-asientos` (parámetro `use_last_rate` de `compute_rate`).
- Código: `l10n_ve_accountant_asset/models/{account_asset,account_move,account_move_line}.py`, la migración y los tests del addon.
- Solo aplica a cuotas de tipo `depreciation`. Fuera de alcance: `negative_revaluation`, `disposal` y `modify` con moneda distinta (se dejan como los devuelve el super; hay un test de que dar de baja sin tasa exacta no falla).
- Sin ninguna tasa anterior a la fecha de adquisición no se crea ninguna cuota y se muestra el `UserError` de tasa no asignada.
- Bases con el modo custom: las cuotas en borrador pasan a `at_date` con su fecha real; los documentos custom que no son de activos pasan a `auto_post='no'` (se listan en el log para que Contabilidad decida); se borran las dos vistas del modo custom.
- Pendiente de validación por Contabilidad: que la tasa de la fecha de adquisición sea el criterio definitivo.
