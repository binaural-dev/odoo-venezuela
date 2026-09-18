## ADDED Requirements

### Requirement: Recompute de disponibilidad de retención ISLR ante cambios en el concepto de pago del producto

El campo `is_isrl_retention_available` de `account.move` SHALL
recalcularse automáticamente cuando cambia el campo `payment_concept` de
cualquier producto usado en `invoice_line_ids`, sin requerir editar la
línea de la factura para forzar el recompute.

#### Scenario: Producto sin concepto de pago al momento de facturar

- **WHEN** se crea una factura con una línea de producto tipo Servicio
  sin `payment_concept` configurado
- **THEN** `is_isrl_retention_available` queda en `False` y la factura no
  aparece en el selector "Retención de" del wizard de Retención de ISLR

#### Scenario: Concepto de pago asignado después de crear la factura

- **WHEN** se asigna `payment_concept` al producto usado en una factura
  ya existente, sin modificar las líneas de esa factura
- **THEN** `is_isrl_retention_available` se recalcula a `True` y la
  factura pasa a estar disponible en el selector "Retención de"
