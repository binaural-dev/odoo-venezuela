## 1. l10n_ve_stock — regla de categorías de producto para sucursales

- [x] 1.1 `product_category_multi_company_rule`: dominio `['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]`
- [x] 1.2 Migración `19.0.1.0.13/post-update_product_category_rule.py` que reescribe el dominio en bases existentes (la regla está en un bloque `noupdate="1"`)
- [x] 1.3 Bump de manifest `l10n_ve_stock` 19.0.1.0.12 → 19.0.1.0.13
- [x] 1.4 Unit tests (`tests/test_product_category_branch_rule.py`): la sucursal ve las de la padre; la sub-sucursal ve las de sus ancestros; una sucursal hermana no ve las de la otra; la padre no ve las de sus sucursales; otra compañía raíz aislada; varias compañías activas suman sus ámbitos

## 2. Verificación (2026-11-18)

Pruebas nuevas, en una BD limpia con `l10n_ve_stock` (las pruebas crean todas sus compañías):

```
odoo -d <bd_limpia> -i l10n_ve_stock --test-tags /l10n_ve_stock:TestProductCategoryBranchRule --stop-after-init --no-http --without-demo=all
```

- [x] 2.1 Resultado: `6 post-tests`, 0 ERROR / 0 FAIL
- [x] 2.2 Control negativo (misma BD, regla original `in company_ids`, sin `-i`): fallan 4 de las 6 (`test_branch_sees_parent_own_and_shared`, `test_grandchild_sees_all_its_ancestors`, `test_sister_branches_do_not_see_each_other`, `test_several_active_companies_add_up`); las otras 2 (padre no ve sucursales, otra raíz aislada) son guardas contra fugas y pasan con ambas reglas

Migración y flujo real, en una copia local de la base de un cliente con sucursal (`-u l10n_ve_stock`):

- [x] 2.3 La migración corre (`Running upgrade [19.0.1.0.13>] post-update_product_category_rule`) y el dominio de la regla queda con `parent_of`
- [x] 2.4 Un usuario solo de la compañía principal valida un envío a Inter-company transit y un usuario con solo la sucursal activa valida la recepción sin "Error de acceso" (antes fallaba con "Categoría del producto (product.category)")
- [x] 2.5 Suite completa `--test-tags /l10n_ve_stock` en esa copia: 281 post-tests, 8 fallos **idénticos con y sin el cambio** (propios de esa base: 4 de `TestProductCompanyEditRestriction` por `FileNotFoundError` del filestore no copiado, `TestProductTemplateTaxesAndPrices.test_write_two_taxes_raises` y `test_prices_without_taxes` por la configuración de impuestos, y 2 de `TestStockScrapActionValidate` por `AccessError` en `alternate_cost`)
- [ ] 2.6 Probar en el staging del cliente: actualizar `l10n_ve_stock` y validar una recepción con solo la sucursal activa
