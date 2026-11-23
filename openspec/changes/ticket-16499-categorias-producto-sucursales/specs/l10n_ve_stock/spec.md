## MODIFIED Requirements

### Requirement: Categorías de producto multi-compañía

El módulo DEBE (MUST) dotar a `product.category` de un campo `company_id` (por defecto la compañía activa) y de una regla de registro global (`product_category_multi_company_rule`, cargada con `noupdate="1"` y actualizada en bases existentes por la migración `19.0.1.0.13`) cuyo dominio es `['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]`. Una compañía DEBE (MUST) ver las categorías propias, las de sus ancestros y las que no tienen compañía, y NO DEBE (MUST NOT) ver las de sus sucursales, las de una sucursal hermana ni las de otra compañía raíz.

#### Scenario: La sucursal ve las categorías de su compañía padre

- **WHEN** un usuario con solo la sucursal activa consulta categorías de la sucursal, de su compañía padre y sin compañía
- **THEN** ve las tres, y puede validar una recepción de productos de la compañía padre sin error de acceso

#### Scenario: Una sub-sucursal ve las de todos sus ancestros

- **WHEN** un usuario con solo una sub-sucursal activa consulta categorías de la sub-sucursal, de su sucursal y de la raíz
- **THEN** ve las tres y las sin compañía

#### Scenario: Una sucursal hermana no ve las categorías de la otra

- **WHEN** un usuario con solo la sucursal 2 activa consulta las categorías de la sucursal 1
- **THEN** no aparecen

#### Scenario: La compañía padre no ve las categorías de sus sucursales

- **WHEN** un usuario con solo la compañía padre activa consulta las categorías de una sucursal
- **THEN** no aparecen

#### Scenario: Una categoría de otra compañía raíz no aparece

- **WHEN** un usuario consulta categorías y existe una con `company_id` de otra compañía raíz (otra persona jurídica)
- **THEN** esa categoría no aparece en sus resultados, aunque el usuario tenga acceso a esa compañía sin tenerla activa

#### Scenario: Con varias compañías activas se suman sus ámbitos

- **WHEN** el usuario tiene activas dos sucursales hermanas
- **THEN** ve las categorías de ambas, las de la padre y las sin compañía
