## Why

Las cuotas de depreciación de un activo se publican en fechas futuras (cron nativo de `auto_post='at_date'`), a veces en días sin tasa cargada, y su importe en moneda alterna cambiaba según la tasa del día de publicación. Contabilidad requiere que el valor alterno de toda la depreciación se calcule con una tasa fija desde que se crea la cuota: la propia del activo si la tiene y, si no, la de la fecha de adquisición (ticket #16384). Una versión previa del addon resolvía la fecha con un modo propio `auto_post='custom'`, que se elimina: las cuotas vuelven a nacer con su fecha real y el `auto_post` nativo.

## What Changes

- Addon nuevo `l10n_ve_accountant_asset` 19.0.1.0.2 (puente, instalación manual —sin `auto_install`—, depende de `l10n_ve_accountant` y `account_asset`, con `i18n/es_VE.po` propio). `binaural_account_asset` NO es dependencia.
- `account.asset._get_acquisition_rate_values()` resuelve la tasa efectiva de las cuotas así: (1) la tasa propia del activo si el campo `foreign_rate` existe en `account.asset` (lo define `binaural_account_asset`) y es > 0, con su `foreign_inverse_rate` (si la inversa falta se deriva con `compute_inverse_rate`); (2) si no, la última tasa de la tabla en `acquisition_date` (`compute_rate(use_last_rate=True)` con la compañía del activo; fin de semana o feriado usan la última tasa anterior); (3) si no hay tasa propia y falta `acquisition_date` lanza `UserError` (guarda defensiva: la base no permite persistir un activo sin fecha porque `prorata_date` es NOT NULL); (4) si no hay ninguna tasa en esa fecha ni antes lanza `UserError` con el activo, la fecha y la moneda. Sin moneda alterna en la compañía devuelve `{}`.
- `account.move._prepare_move_for_asset_depreciation`: las cuotas `asset_move_type == 'depreciation'` nacen con `manually_set_rate=True` y `foreign_rate`/`foreign_inverse_rate` de la tasa efectiva. Al ser tasa manual, no se recalcula al publicar.
- `account.move.line._get_non_invoice_foreign_value`: el USD de las líneas de una cuota es `(debit - credit) / foreign_rate` de la cuota (siguiendo la cadena de `reversed_entry_id` para los reversos); no usa `foreign_inverse_rate`, que está truncado a 6 decimales en el activo.
- `account.asset.compute_depreciation_board`: solo escribe la tasa en el activo (si el campo existe) cuando este NO tiene tasa propia, para que la escritura de `binaural_account_asset` copie el mismo valor sea cual sea el orden del MRO; restaura las cuotas ya publicadas a su tasa previa y corrige solo las cuotas nuevas cuya tasa difiera. Solo escribe si algo cambia.
- Las cuotas futuras nacen con su fecha real y el `auto_post='at_date'` nativo, sin modo propio.
- Migración `migrations/19.0.1.0.2/pre-10-remove_custom_auto_post.py` para bases que tuvieron el modo `auto_post='custom'`.

## Impact

- Specs afectadas: nueva `l10n_ve_accountant_asset` (se AÑADE; no existía). Es el único llamador de `compute_rate(use_last_rate=True)` (parámetro que conserva `l10n_ve_rate`; ver el change `ti-16384-tasa-exacta-al-publicar-asientos`). `l10n_ve_accountant` ya no lo usa.
- Código: `l10n_ve_accountant_asset/models/{account_asset,account_move,account_move_line}.py`, la migración, `i18n/es_VE.po` y los tests del addon.
- Cambio respecto a la versión anterior de este spec: la tasa de la tabla en la fecha de adquisición manda sobre la de la factura de compra SOLO cuando el activo no tiene tasa propia; con tasa propia (`binaural_account_asset`) las cuotas usan esa tasa.
- Solo aplica a cuotas de tipo `depreciation`. Las bajas (`disposal`), revalorizaciones y `modify` con moneda distinta se dejan como las devuelve el super: siguen la regla de asiento manual de `l10n_ve_accountant` (tasa exacta al publicar) salvo con `binaural_account_asset`, que escribe la tasa del activo en todos los tipos de asiento.
- `compute_depreciation_board(date)` de `binaural_account_asset` real no acepta `date` (error previo, se atiende en un ticket aparte); por eso los tests que ejecutan `modify` o recálculo con fecha se omiten cuando ese addon está instalado.
- Sin tasa propia y sin ninguna tasa en la fecha de adquisición ni antes, no se crea ninguna cuota y se muestra el `UserError`.
- Bases con el modo custom: las cuotas en borrador pasan a `at_date` con su fecha real; los documentos custom que no son de activos pasan a `auto_post='no'` (se listan en el log para que Contabilidad decida); se borran las dos vistas del modo custom.
- `integra-addons` NO se modifica en este PR (decisión: evitar complicar la revisión con un PR en otro repositorio). Estos cambios se requieren a la brevedad para poder confirmar los asientos de depreciación de activos fijos.
- Pendiente de validación por Contabilidad: que la tasa propia del activo y, en su defecto, la de la fecha de adquisición sea el criterio definitivo.
