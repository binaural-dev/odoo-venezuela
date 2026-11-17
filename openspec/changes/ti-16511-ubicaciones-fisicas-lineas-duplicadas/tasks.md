## 1. l10n_ve_stock — una línea por ubicación

- [x] 1.1 Restricción `UNIQUE(stock_alter_location_id, location_id)` en `stock.picking.alter.location.line` con mensaje traducido en `es_VE.po`
- [x] 1.2 `_get_quants_for_alter_lines` agrupa los quants por ubicación
- [x] 1.3 Migración `19.0.1.0.13/pre-migrate.py` que fusiona duplicados sumando cantidades; bump del manifest
- [x] 1.4 Pruebas en `tests/test_alter_location_unique.py` (tag `l10n_ve_stock_alter_location_unique`), cinco clases:
  - `TestAlterLocationLineConstraint`: la restricción existe en la base con su definición y su xmlid traducible; rechaza el duplicado por `create`, dentro del mismo `create`, desde el formulario (`Form`), al cambiar la ubicación de una línea y por importación (`load`); permite la misma ubicación en otro registro y reutilizar una ubicación liberada.
  - `TestAlterLinesFromQuants`: suma por ubicación con paquetes y con lotes; ignora quants en cero o negativos; descuenta lo reservado; excluye otros almacenes; resuelve el almacén desde la ubicación; sin almacén o sin quants no devuelve líneas; los dos llamadores (`_sync_alter_locations_from_physical_locations`, `_create_or_update_alter_location`) crean una línea por ubicación.
  - `TestAlterFlowsKeepOneLine`: recepción, salida (dos veces), entrega desde Salida, transferencia interna, wizard, sincronización con quants, registro de ubicación y libro de reubicación actualizan la línea existente sin duplicar.
  - `TestPickingWithPackagesRegression`: punta a punta del error original, con producto en dos paquetes en su ubicación física, pick hacia Salida y entrega al cliente.
  - `TestMergeDuplicatedLinesMigration`: suma sin alterar totales, conserva el menor `id`, varios grupos y registros, cantidades negativas y vacías, líneas sin registro o sin ubicación intactas, sin duplicados no cambia ni registra nada, deja log auditable, la restricción se puede crear después, `migrate()` corre en upgrade y no en instalación.

## 2. Verificación

- [x] 2.1 Correr las pruebas de `l10n_ve_stock` tras el upgrade del módulo: 318 pruebas post-install, 0 fallos, 0 errores (maxcam-ext, base nueva)
- [x] 2.1.1 Cobertura (líneas y ramas): `stock_picking_alter_location_line.py` 100 %; `_get_quants_for_alter_lines` 100 % (las 3 ramas sin cubrir de `product_template.py` están en `_transfer_between_locations`, fuera de este cambio); `migrations/19.0.1.0.13/pre-migrate.py` 100 % medido aparte, porque el `.coveragerc` estándar omite `*/migrations/*`; módulo completo 93 %
- [x] 2.1.2 Mutación: sin la agrupación por ubicación fallan 5 de las 11 pruebas de `TestAlterLinesFromQuants` + `TestPickingWithPackagesRegression`
- [ ] 2.2 Upgrade sobre una copia de base con duplicados (no producción): la restricción queda creada y los totales de los registros afectados no cambian
- [ ] 2.3 Reintentar la validación del picking que fallaba en la copia
