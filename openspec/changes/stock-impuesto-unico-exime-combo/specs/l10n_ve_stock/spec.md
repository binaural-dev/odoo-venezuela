## MODIFIED Requirements

### Requirement: Un solo impuesto de venta por compañía en el producto

El sistema DEBE (MUST) validar, en `create` y en `write` de `taxes_id` de `product.template` (método `_validate_single_sale_tax`), que el producto no tenga más de un impuesto de venta por compañía. Los productos de tipo `combo` DEBEN (MUST) quedar exentos de esta validación, porque no llevan impuestos propios (los toman de sus componentes), igual que en la regla de impuesto único de `l10n_ve_accountant`.

#### Scenario: Segundo impuesto de la misma compañía

- **WHEN** se asignan dos impuestos de venta de la misma compañía a un producto que no es combo
- **THEN** se lanza un error indicando que el producto debe tener un solo impuesto

#### Scenario: Combo con varios impuestos

- **WHEN** se crea un producto combo con dos impuestos de venta de la misma compañía, o se le asignan por `write`
- **THEN** el producto se guarda sin error de impuesto único
