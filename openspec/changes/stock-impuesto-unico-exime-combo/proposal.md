## Why

`l10n_ve_accountant` exime a los productos combo de la regla "exactamente un impuesto por producto" (#14405): el combo no lleva impuestos propios, los toma de sus componentes. Pero `l10n_ve_stock` tiene su propia validación (`_validate_single_sale_tax`, #13905) que corre después del `create` y del `write` de `taxes_id` sin esa excepción, así que con los dos módulos instalados un combo con más de un impuesto de venta sigue sin poder guardarse.

Se nota en el CI en modo integración: cuando un PR toca `l10n_ve_pos` (que depende de `l10n_ve_stock`) junto con `l10n_ve_accountant`, los tests de combos de `l10n_ve_accountant` (`test_product_template` 15, 16, 17 y 20) fallan con `ValidationError: This product must have only one tax.` (PR #1326, ticket #15114).

## What Changes

- `l10n_ve_stock`: `_validate_single_sale_tax` salta los productos de tipo `combo`, igual que la validación de `l10n_ve_accountant`. Para el resto de tipos la regla no cambia.

## Impact

- Specs afectadas: `l10n_ve_stock` (se MODIFICA la requirement "Un solo impuesto de venta por compañía en el producto").
- Código: `l10n_ve_stock/models/product_template.py` (`_validate_single_sale_tax`). Bump del manifest a 19.0.1.0.9.
- Pasar un combo a otro tipo con dos impuestos sigue bloqueado por `l10n_ve_accountant` (`_enforce_single_tax_vals`).
