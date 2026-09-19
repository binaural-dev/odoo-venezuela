# Spec delta: pos-refund-original-rate

## ADDED Requirements

### Requirement: El monto en divisa de la línea del PdV respeta la config de visualización de impuestos

El sistema SHALL mostrar el monto en divisa de una línea del PdV usando el
precio CON impuesto (`get_foreign_price_with_tax()`) cuando
`pos.config.iface_tax_included` es `'total'`, y el precio SIN impuesto
(`get_foreign_price_without_tax()`) en caso contrario, de modo que la columna
en divisa coincida con lo que el core muestra en la columna local para la
misma configuración.

#### Scenario: PdV con impuesto separado (subtotal)

- **GIVEN** un PdV con `iface_tax_included = 'subtotal'`
- **WHEN** se renderiza una línea con impuesto
- **THEN** el monto en divisa se muestra SIN impuesto, igual que el precio
  local de esa línea

#### Scenario: PdV con impuesto incluido (total)

- **GIVEN** un PdV con `iface_tax_included = 'total'` (por defecto)
- **WHEN** se renderiza una línea con impuesto
- **THEN** el monto en divisa se muestra CON impuesto, sin cambios de
  comportamiento
