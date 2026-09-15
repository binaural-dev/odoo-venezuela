# Spec delta: retention-accounting-date-validation

## MODIFIED Requirements

### Requirement: La fecha contable de una retención no puede ser anterior a la de ninguna de sus facturas

El sistema SHALL bloquear tanto el guardado (`create`/`write`, vía
`@api.constrains`) como la emisión (`action_post()`) de `account.retention`
con un `ValidationError` cuando **`date_accounting` o `date` (Fecha de
Comprobante)** sea anterior a la fecha de factura (`invoice_date_display or
invoice_date`) de **cualquiera** de las facturas referenciadas en
`retention_line_ids.move_id` — no solo de la más antigua. La comparación
SHALL hacerse contra la fecha de factura más reciente entre todas las
líneas de la retención, para cada uno de los dos campos de fecha por
separado.

> Extiende el requisito original de este mismo nombre (helpdesk
> #15019/#14984, ver `openspec/changes/retention-accounting-date-validation/`):
> ese change solo cubría `date_accounting`. Helpdesk #15188 reportó que
> `date` (Fecha de Comprobante) quedaba sin ninguna validación - se podía
> editar a una fecha anterior a la factura y aprobar la retención sin
> bloqueo. Este delta agrega `date` a la misma regla, reusando
> `_get_max_invoice_date()` sin cambios.

Motivo: igual que `date_accounting`, `date` es una fecha del hecho
generador de la retención (la factura) - contabilizar o fechar el
comprobante antes de que exista la factura que lo origina viola el orden
causal de los hechos económicos.

#### Scenario: Fecha de Comprobante anterior a la factura

- **GIVEN** una retención con una línea sobre una factura cuyo
  `invoice_date_display` es `2026-08-31`
- **WHEN** se intenta guardar la retención con `date` = `2026-08-29`
- **THEN** se lanza `ValidationError` con un mensaje que indica que la
  fecha de comprobante no puede ser anterior a la fecha de factura,
  nombrando la factura
- **AND** el cambio no se persiste

#### Scenario: Fecha Contable anterior a la factura (sin regresión)

- **GIVEN** la misma retención del escenario anterior
- **WHEN** se intenta guardar la retención con `date_accounting` =
  `2026-08-29` (en vez de `date`)
- **THEN** se lanza `ValidationError` con el mensaje de `date_accounting`
  (comportamiento sin cambios respecto al change original de
  #15019/#14984)

#### Scenario: Fecha de Comprobante igual a la fecha de factura

- **GIVEN** una retención con `date` igual a la fecha de todas las
  facturas de sus líneas
- **WHEN** se guarda o se ejecuta `action_post()`
- **THEN** la validación de fecha no bloquea (el límite es inclusivo,
  igual que para `date_accounting`)

#### Scenario: Aprobar con Fecha de Comprobante inconsistente

- **GIVEN** una retención con `date` anterior a la fecha de la factura de
  alguna de sus líneas (guardada antes de que existiera esta validación, o
  editada por escritura directa que de alguna forma evadiera el
  `@api.constrains`)
- **WHEN** se ejecuta `action_post()`
- **THEN** se lanza `ValidationError` y la retención NO queda `emitted` -
  mismo comportamiento que ya tenía `date_accounting`, porque
  `action_post()` llama al mismo helper
  (`_check_accounting_date_vs_invoices()`) que ahora valida ambos campos
