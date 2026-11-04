# Spec delta: block-iva-supplier-retention-line-amounts

## ADDED Requirements

### Requirement: Los montos de una línea de retención de IVA de proveedor deben ser de solo lectura

El sistema SHALL mostrar `invoice_total`, `invoice_amount`,
`iva_amount` y `retention_amount` como campos de solo lectura (con su
valor preservado al guardar, vía `force_save`) en cada línea de
`account.retention.line` cuando la retención (`account.retention.type`)
sea de proveedor (`in_invoice`, `in_refund` o `in_debit`).

Para retenciones de cliente (`out_invoice`, `out_refund`, `out_debit`)
estos campos SHALL permanecer editables, sujeto solo a las reglas de
`state` ya existentes.

#### Scenario: Retención de proveedor

- **GIVEN** una retención de IVA con `type = 'in_invoice'`
- **WHEN** se abre su formulario
- **THEN** `invoice_total`, `invoice_amount`, `iva_amount` y
  `retention_amount` de cada línea SHALL aparecer de solo lectura

#### Scenario: Retención de cliente

- **GIVEN** una retención de IVA con `type = 'out_invoice'`
- **WHEN** se abre su formulario
- **THEN** `invoice_total`, `invoice_amount`, `iva_amount` y
  `retention_amount` de cada línea SHALL seguir siendo editables
  (según el estado de la retención)
