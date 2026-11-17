## 1. l10n_ve_stock — una línea por ubicación

- [x] 1.1 Restricción `UNIQUE(stock_alter_location_id, location_id)` en `stock.picking.alter.location.line` con mensaje traducido en `es_VE.po`
- [x] 1.2 `_get_quants_for_alter_lines` agrupa los quants por ubicación
- [x] 1.3 Migración `19.0.1.0.13/pre-migrate.py` que fusiona duplicados sumando cantidades (sale si la tabla no existe, borra `ir_model_data` de las líneas eliminadas, actualiza `write_date`) y `post-migrate.py` que deja la nota en el chatter; bump del manifest
- [x] 1.4 Pruebas en `tests/test_alter_location_unique.py` (tag `l10n_ve_stock_alter_location_unique`), cinco clases:
  - `TestAlterLocationLineConstraint`: la restricción existe en la base con su definición y su xmlid traducible; rechaza el duplicado por `create`, dentro del mismo `create`, desde el formulario (`Form`), al cambiar la ubicación de una línea y por importación (`load`); permite la misma ubicación en otro registro y reutilizar una ubicación liberada.
  - `TestAlterLinesFromQuants`: suma por ubicación con paquetes y con lotes; ignora quants en cero o negativos; descuenta lo reservado; excluye otros almacenes; resuelve el almacén desde la ubicación; sin almacén o sin quants no devuelve líneas; los dos llamadores (`_sync_alter_locations_from_physical_locations`, `_create_or_update_alter_location`) crean una línea por ubicación.
  - `TestAlterFlowsKeepOneLine`: recepción, salida (dos veces), entrega desde Salida, transferencia interna, wizard, sincronización con quants, registro de ubicación y libro de reubicación actualizan la línea existente sin duplicar.
  - `TestPickingWithPackagesRegression`: punta a punta del error original, con producto en dos paquetes en su ubicación física, pick hacia Salida y entrega al cliente.
  - `TestMergeDuplicatedLinesMigration`: suma sin alterar totales, conserva el menor `id`, varios grupos y registros, cantidades negativas y vacías, líneas sin registro o sin ubicación intactas, sin duplicados no cambia ni registra nada, deja log auditable, la restricción se puede crear después, `migrate()` corre en upgrade y no en instalación, sin tabla (anterior a 19.0.1.0.6) no hace nada, borra `ir_model_data` de las líneas eliminadas, actualiza `write_date`.
  - `TestMergedLinesChatterMigration`: nota en el chatter de cada registro fusionado y no en los demás, en el idioma del administrador (es_VE), salta registros borrados, sin fusiones no publica nada, no corre en instalación nueva.
  - Además: mensaje de la restricción en es_VE al importar y suma de quants redondeada con la unidad de medida.

## 2. Verificación

- [x] 2.1 Correr las pruebas de `l10n_ve_stock` (`./odoo test maxcam-ext l10n_ve_stock --no-confirm --out-coverage-json <ruta>`, base nueva): 328 pruebas post-install, 0 fallos, 0 errores
- [x] 2.1.1 Cobertura (líneas y ramas): `stock_picking_alter_location_line.py` 100 %; `_get_quants_for_alter_lines` y `_post_merged_lines_message` 100 % (lo no cubierto de `product_template.py` y `stock_picking_alter_location.py` está en `_transfer_between_locations` y `subtract_physical_quantity`, fuera de este cambio); `pre-migrate.py` y `post-migrate.py` 100 % medidos aparte, porque el `.coveragerc` estándar omite `*/migrations/*`; módulo completo 93 %
- [x] 2.1.2 Mutación: sin la agrupación por ubicación fallan 5 de las 11 pruebas de `TestAlterLinesFromQuants` + `TestPickingWithPackagesRegression`
- [x] 2.2 Upgrade sobre una copia local de Maxcam con duplicados reales (`maxcam-ext-ti16511`, datos al 27-10-2026; no producción), con `./odoo update maxcam-ext -d maxcam-ext-ti16511 -m l10n_ve_stock`: corren pre y post, se fusionan los 9 grupos, la restricción queda en `pg_constraint`, quedan 0 duplicados, el total de líneas baja en 9 sin cambiar la suma de cantidades ni los totales por registro, cada registro afectado tiene su nota en español y la tabla temporal no queda
- [ ] 2.3 Reintentar la validación del picking que fallaba: requiere una copia de producción posterior al error, porque las líneas del traceback (180723, 195589) no existen en la copia del 27-10
