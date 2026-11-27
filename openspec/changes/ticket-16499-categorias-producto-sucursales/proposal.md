## Why

Un usuario con solo una **sucursal** activa (compañía hija) no puede validar una recepción de productos de la compañía principal: falla con "Error de acceso: Categoría del producto (product.category)". Al validar, `stock_account` recalcula el costo del producto y lee `categ_id.property_cost_method` con los permisos del usuario; la regla `product_category_multi_company_rule` filtraba por `company_id in company_ids`, que no incluye a la compañía padre, así que la categoría quedaba fuera del alcance de la sucursal. Solo funcionaba con ambas compañías activas. El core ya usa `parent_of` en las reglas de `product.template` y `product.product`; esta regla no seguía ese criterio. (Ticket #16499.)

## What Changes

- `l10n_ve_stock`: la regla global `product_category_multi_company_rule` pasa a `['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]`. Cada compañía ve las categorías propias, las de sus ancestros y las que no tienen compañía.
- Migración `19.0.1.0.13`: la regla vive en un bloque `noupdate="1"`, así que el XML no actualiza las bases existentes; la migración reescribe el dominio. Bump de manifest 19.0.1.0.12 → 19.0.1.0.13.
- La regla sigue siendo unidireccional: la compañía padre no ve las categorías de sus sucursales, ni una sucursal las de su hermana, ni nadie las de otra compañía raíz.

## Impact

- Specs afectadas: `l10n_ve_stock` (requirement "Categorías de producto multi-compañía", MODIFIED).
- Código: `l10n_ve_stock/security/security_l10n_ve_stock.xml`, `l10n_ve_stock/migrations/19.0.1.0.13/post-update_product_category_rule.py`, `l10n_ve_stock/__manifest__.py`.
- La regla es global y aplica a lectura, escritura, creación y borrado: un usuario con permiso de gestor de productos y solo la sucursal activa puede editar categorías de la compañía padre (misma semántica que el core en `product.template`).
- Las reglas de `stock.picking.alter.location` y su línea, del mismo archivo, NO cambian: son documentos de operación (su `company_id` sale del almacén) y con `parent_of` la sucursal vería y podría editar los de la compañía padre.
- Datos existentes: solo cambia qué categorías ve cada compañía; no se modifican registros.
