## ADDED Requirements

### Requirement: base_amount por grupo de impuesto coincide con el balance real

Cuando una factura (`account.move`, `out_invoice`/`in_invoice`/`out_refund`/`in_refund`) está en una moneda distinta a la de la compañía y tiene dos o más grupos de impuesto (`account.tax.group`) distintos, el sistema DEBE (MUST) reportar en `tax_totals` (el campo que alimenta el widget de la factura y el PDF) un `base_amount` (moneda de la compañía) por cada `tax_group` que coincida, al céntimo, con la suma real del `balance` de las líneas de producto (`account.move.line`, `display_type='product'`) que pagan ese impuesto — directamente o, para un impuesto tipo 'group', a través de sus `children_tax_ids`.

El total agregado de la factura y el reparto entre subtotales (cuando existe cash rounding) NO DEBEN (MUST NOT) cambiar respecto al comportamiento ya corregido. Como respaldo defensivo, si no se pueden identificar las líneas propias de un grupo, el sistema puede recurrir al reparto proporcional del diferencial agregado.

#### Scenario: Dos grupos de impuesto distintos en una factura de proveedor

- **WHEN** una factura de proveedor en USD (compañía en VEF) tiene una línea exenta (0%, grupo propio) y otra al 16% (otro grupo), con una tasa BCV de varios decimales
- **THEN** el `base_amount` de cada `tax_group` en `tax_totals` coincide con el `balance` real posteado de su propia línea, no con un reparto proporcional del diferencial agregado

#### Scenario: Mismo escenario en una factura de cliente

- **WHEN** el mismo escenario ocurre en una factura de cliente (`out_invoice`)
- **THEN** el `base_amount` de cada grupo también coincide con el balance real, sin distinción por dirección del documento

#### Scenario: Tres o más grupos distintos

- **WHEN** una factura tiene tres grupos de impuesto distintos (no solo dos)
- **THEN** el grupo del medio (no solo el primero o el último) también coincide con su balance real

#### Scenario: Impuesto tipo 'group' con hijos que comparten base

- **WHEN** una línea usa un impuesto tipo 'group' (dos hijos porcentuales que comparten la misma base), combinado con un grupo de impuesto independiente en otra línea
- **THEN** el sistema identifica las líneas de cada grupo también a través de `children_tax_ids`, y ambos grupos reportados coinciden con su balance real
