# l10n_ve_invoice_loyalty

## Purpose

Puente entre la facturación venezolana y el programa de lealtad estándar de Odoo. Extiende `account.move` sobrescribiendo el constraint `_check_price_in_zero` de `l10n_ve_invoice` para que las líneas de descuento generadas por recompensas de lealtad no bloqueen la validación de precios en cero. Depende de `l10n_ve_invoice` y `loyalty`. El módulo no aporta datos, vistas ni seguridad: solo el método sobrescrito.

## Requirements

### Requirement: Exención del precio en cero cuando hay una línea de recompensa de lealtad

El constraint `_check_price_in_zero` sobrescrito DEBE (MUST) recorrer las líneas (`invoice_line_ids`) de las facturas del recordset y detenerse en la **primera** línea con `price_unit <= 0` cuyo `display_type` no sea `line_section` ni `line_note`; si el producto de esa línea está registrado como `discount_line_product_id` de alguna `loyalty.reward`, DEBE (MUST) delegar en el constraint de `l10n_ve_invoice` con el contexto `from_loyalty=True` (que lo exime del error) y, en caso contrario, delegar sin ese contexto (dejando que la validación base decida). En ambos casos el método retorna al delegar, por lo que la decisión se toma con una sola línea y el resultado aplica a **todo el recordset**, no línea por línea.

#### Scenario: Factura con línea de recompensa en cero

- **WHEN** una factura contiene una única línea con precio 0 cuyo producto está registrado como `discount_line_product_id` de alguna `loyalty.reward`
- **THEN** la factura se valida sin error de precio en cero

#### Scenario: Línea en cero de un producto ordinario

- **WHEN** la primera línea no positiva de la factura es de un producto que no corresponde a ninguna recompensa de lealtad ni a una línea de descuento reconocida por `l10n_ve_invoice`
- **THEN** se lanza el error de validación de `l10n_ve_invoice` indicando que una factura no puede tener líneas con precio cero

#### Scenario: Recompensa y línea ordinaria en cero en la misma factura

- **WHEN** una factura tiene una línea de recompensa en 0 antes de una línea ordinaria en 0
- **THEN** no se lanza ningún error, porque la exención `from_loyalty=True` se aplica al recordset completo y el recorrido termina en la línea de recompensa

#### Scenario: Línea ordinaria en cero antes de la recompensa

- **WHEN** la primera línea no positiva es de un producto ordinario y más abajo existe una línea de recompensa en 0
- **THEN** se lanza el error de precio en cero, porque la decisión se toma con la primera línea encontrada

### Requirement: Reconocimiento de la recompensa por búsqueda global de `loyalty.reward`

El reconocimiento de la línea como recompensa DEBE (MUST) hacerse con un `search_count` sobre `loyalty.reward` filtrando únicamente por `discount_line_product_id = line.product_id.id`: no se verifica que la recompensa pertenezca al programa, al pedido ni a la compañía de la factura, ni que la línea provenga realmente de una recompensa aplicada. Basta con que exista cualquier `loyalty.reward` en la base de datos apuntando a ese producto para que la factura completa quede exenta.

#### Scenario: Producto de recompensa vendido manualmente

- **WHEN** un usuario agrega manualmente, con precio 0, un producto que es `discount_line_product_id` de una recompensa de otro programa o de otra compañía
- **THEN** la validación de precio en cero no se aplica, porque la búsqueda solo compara el producto

#### Scenario: Línea sin producto

- **WHEN** la primera línea no positiva no tiene producto y existe alguna `loyalty.reward` sin `discount_line_product_id`
- **THEN** la búsqueda encuentra coincidencia y la factura queda exenta del error de precio en cero
