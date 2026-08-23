# l10n_ve_invoice_loyalty

## Purpose

Puente entre la facturación venezolana y el programa de lealtad estándar de Odoo. Extiende `account.move` para que la validación de precios en cero de `l10n_ve_invoice` no bloquee las líneas de descuento generadas por recompensas de lealtad. Depende de `l10n_ve_invoice` y `loyalty`.

## Requirements

### Requirement: Permitir líneas en cero de recompensas de lealtad

El sistema DEBE (MUST) permitir líneas de factura con `price_unit` menor o igual a cero cuando el producto de la línea es el producto de descuento de una recompensa de lealtad (`loyalty.reward.discount_line_product_id`): en ese caso el constraint `_check_price_in_zero` re-ejecuta la validación de `l10n_ve_invoice` con el contexto `from_loyalty=True`, que la exime del error. Para líneas en cero cuyo producto no es una recompensa (ni una línea de descuento reconocida por `l10n_ve_invoice`), la validación base sigue aplicando.

#### Scenario: Factura con línea de recompensa en cero

- **WHEN** una factura contiene una línea con precio 0 cuyo producto está registrado como `discount_line_product_id` de alguna `loyalty.reward`
- **THEN** la factura se valida sin error de precio en cero

#### Scenario: Línea en cero de un producto ordinario

- **WHEN** una factura contiene una línea con precio 0 de un producto que no corresponde a ninguna recompensa de lealtad ni a una línea de descuento reconocida
- **THEN** se lanza el error de validación de `l10n_ve_invoice` indicando que una factura no puede tener líneas con precio cero
