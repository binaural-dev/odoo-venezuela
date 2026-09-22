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

### Requirement: Nombre del destinatario solo en pickings de salida, usando `display_name`

El template `packaging_picking_item` DEBE (MUST) mostrar el nombre del partner solo cuando el `picking` es de tipo salida (`picking_type_id.code == 'outgoing'`) y tiene un `partner_id` seteado, y DEBE (MUST) usar `partner_id.display_name` en vez de `partner_id.name`, a pedido explícito del cliente.

Antes de este requirement, el template evaluaba `picking.partner_id.name[:80]` sin verificar el tipo de picking ni la existencia de `partner_id`. En un picking sin `picking_type_id.code == 'outgoing'` con `partner_id` vacío, `picking.partner_id` resuelve a `False` (recordset vacío en booleano), y `False.name` no es un `TypeError` de slicing directo, pero el patrón `False[:80]` sobre el resultado de encadenar en un campo vacío sí produce un `TypeError: 'bool' object is not subscriptable` en runtime — confirmado en logs de staging (`RPC_ERROR`) al imprimir una etiqueta para un picking de salida sin `partner_id` asignado.

#### Scenario: Picking de salida con partner asignado

- **WHEN** se imprime la etiqueta para un picking con `picking_type_id.code == 'outgoing'` y `partner_id` seteado
- **THEN** el reporte muestra el `display_name` del partner (recortado a 80 caracteres) en la parte superior de la etiqueta

#### Scenario: Picking de salida sin partner asignado

- **WHEN** se imprime la etiqueta para un picking con `picking_type_id.code == 'outgoing'` y `partner_id` vacío
- **THEN** el reporte no muestra la línea del nombre del destinatario (el `t-if` la omite) y no lanza `TypeError`

#### Scenario: Picking que no es de salida (ej. interno, recepción)

- **WHEN** se imprime la etiqueta para un picking con `picking_type_id.code` distinto de `'outgoing'`
- **THEN** el reporte no muestra la línea del nombre del destinatario, independientemente de si `partner_id` está seteado
