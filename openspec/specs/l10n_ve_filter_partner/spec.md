# l10n_ve_filter_partner

## Purpose

Módulo técnico que provee el mixin abstracto `filter.partner.mixin` para filtrar el dominio de campos de contacto según el tipo de relación (cliente, proveedor o contacto puro). Otros módulos de la localización lo heredan en sus modelos para restringir qué contactos se pueden seleccionar. Depende solo de `web`.

## Requirements

### Requirement: Mixin de filtro de contactos

El mixin `filter.partner.mixin` DEBE (MUST) exponer el campo de selección `filter_partner` con los valores `customer` (Cliente), `supplier` (Proveedor) y `contact` (Contacto), y el campo calculado `partner_id_domain` (Char) que contiene, en formato JSON, el dominio de contactos correspondiente al valor seleccionado.

#### Scenario: Modelo que hereda el mixin

- **WHEN** un modelo hereda `filter.partner.mixin` y establece `filter_partner`
- **THEN** `partner_id_domain` se recalcula con el dominio JSON correspondiente

### Requirement: Dominio por tipo de relación

El dominio calculado DEBE (MUST) corresponder al tipo seleccionado: `customer` filtra `customer_rank >= 1`, `supplier` filtra `supplier_rank >= 1`, `contact` filtra `customer_rank = 0` y `supplier_rank = 0`, y sin valor seleccionado el dominio es vacío (sin restricción).

#### Scenario: Filtro de clientes

- **WHEN** `filter_partner` es `customer`
- **THEN** el dominio resultante es `[("customer_rank", ">=", 1)]`

#### Scenario: Sin filtro

- **WHEN** `filter_partner` no tiene valor
- **THEN** el dominio resultante es la lista vacía

### Requirement: Extensión del dominio con condiciones adicionales

El método `get_partner_domain(extend, conditional)` DEBE (MUST) combinar el dominio del tipo seleccionado con dominios adicionales: con `conditional="&"` (valor por defecto) los une con AND, con cualquier otro valor los une con OR; sin `extend` devuelve solo el dominio del tipo.

#### Scenario: Extensión con AND

- **WHEN** se invoca `get_partner_domain(extend=[...])` sin cambiar `conditional`
- **THEN** devuelve la conjunción (AND) del dominio del tipo con el dominio extra
