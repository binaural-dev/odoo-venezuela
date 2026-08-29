## ADDED Requirements

### Requirement: Impresión de etiquetas de embalaje aunque `package_qty` esté sin setear

El reporte `l10n_ve_stock.action_packaging_picking` DEBE (MUST) imprimir al menos una etiqueta de embalaje por traslado incluso cuando `package_qty` del `stock.picking` es 0, `False`/`None` o negativo, tratando esos casos como si fuera 1 paquete. El template padre `packaging_picking` calcula el rango de páginas a imprimir con `range(1, (picking.package_qty if picking.package_qty and picking.package_qty > 0 else 1) + 1)`; el fallback vive en ese cálculo, no dentro de `packaging_picking_item`, porque cualquier guard puesto ahí nunca se alcanza (el `t-foreach` del padre ya descartó la iteración antes de invocar ese sub-template).

#### Scenario: Picking sin `package_qty` seteado

- **WHEN** se imprime "Packaging tags" para un traslado con `package_qty` igual a 0
- **THEN** el reporte imprime una etiqueta, mostrando "Package 1 / 1"

#### Scenario: Picking con `package_qty` negativo

- **WHEN** `package_qty` es un valor negativo
- **THEN** el reporte igual imprime una etiqueta como si fuera 1 paquete, sin lanzar error

#### Scenario: Picking con `package_qty` mayor a 1

- **WHEN** `package_qty` es 3
- **THEN** el reporte imprime 3 etiquetas, numeradas "Package 1 / 3", "Package 2 / 3", "Package 3 / 3"
