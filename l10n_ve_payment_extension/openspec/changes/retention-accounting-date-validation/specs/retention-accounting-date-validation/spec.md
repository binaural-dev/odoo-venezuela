# Spec delta: retention-accounting-date-validation

## ADDED Requirements

### Requirement: La fecha contable de una retención no puede ser anterior a la de ninguna de sus facturas

El sistema SHALL bloquear tanto el guardado (`create`/`write`, vía
`@api.constrains`) como la emisión (`action_post()`) de `account.retention`
con un `ValidationError` cuando `date_accounting` sea anterior a la fecha de
factura (`invoice_date_display or invoice_date`) de **cualquiera** de las
facturas referenciadas en `retention_line_ids.move_id` — no solo de la más
antigua. La comparación SHALL hacerse contra la fecha de factura más
reciente entre todas las líneas de la retención.

Motivo: una retención es consecuencia contable/fiscal de una factura ya
emitida; contabilizarla con fecha anterior a cualquiera de las facturas que
la origina viola el orden causal de los hechos económicos y no tiene forma
de sostenerse ante una fiscalización. El bloqueo debe ocurrir al guardar,
no solo al aprobar, para que la inconsistencia nunca quede persistida.

#### Scenario: Fecha contable anterior a la factura

- **GIVEN** una retención con una línea sobre una factura cuyo
  `invoice_date_display` es `2026-08-31`
- **WHEN** se intenta guardar la retención con `date_accounting` =
  `2026-08-29`
- **THEN** se lanza `ValidationError` con un mensaje que indica que la
  fecha contable no puede ser anterior a la fecha de factura, nombrando la
  factura
- **AND** el cambio no se persiste

#### Scenario: Fecha contable igual a la fecha de factura

- **GIVEN** una retención con `date_accounting` igual a la fecha de todas
  las facturas de sus líneas
- **WHEN** se guarda o se ejecuta `action_post()`
- **THEN** la validación de fecha no bloquea (el límite es inclusivo: igual
  se permite, solo anterior se bloquea)

#### Scenario: Retención con líneas de varias facturas con distinta fecha

- **GIVEN** una retención con líneas sobre dos facturas, una del
  `2026-08-20` y otra del `2026-08-31`
- **AND** `date_accounting` es `2026-08-25`
- **WHEN** se guarda la retención o se ejecuta `action_post()`
- **THEN** se lanza `ValidationError`, porque `2026-08-25` es anterior a la
  fecha de la factura más reciente (`2026-08-31`), aunque sea posterior a
  la más antigua (`2026-08-20`)

#### Scenario: Retención sin líneas o sin fecha de factura

- **GIVEN** una retención sin `retention_line_ids`, o cuyas facturas no
  tienen `invoice_date_display` ni `invoice_date`
- **WHEN** se guarda la retención
- **THEN** la validación de fecha no bloquea (no hay contra qué comparar)

#### Scenario: Flujo automatizado (cron)

- **GIVEN** `action_post()` ejecutado sobre un recordset con contexto
  `automated_action` o `cron_id`, donde una de las retenciones tiene fecha
  contable inconsistente
- **WHEN** se detecta la inconsistencia
- **THEN** el sistema SHALL registrar el error en el chatter de la
  retención infractora (`message_post` con `category='exception'`) y
  `action_post()` retorna `False` para el método completo — las
  retenciones restantes del recordset que no se hayan procesado aún NO se
  emiten en esa llamada. Es el mismo comportamiento (y la misma
  limitación) que ya tiene la validación existente de monto de retención
  vs. factura; este cambio no la corrige, solo la replica.

#### Scenario: Aclaración — líneas de retención "canceladas" no afectan el cálculo

- **GIVEN** `_get_max_invoice_date()` corre sobre una sola retención
  (`self.ensure_one()`)
- **WHEN** se evalúa `retention_line_ids.move_id`
- **THEN** el sistema NO necesita filtrar por `state` de línea: `state` en
  `account.retention.line` es `related="retention_id.state"`, así que todas
  las líneas de una misma retención comparten siempre el mismo valor — no
  hay forma de que una parte de las líneas esté "cancelada" y otra no
  dentro de una misma retención
- **AND** este flujo tampoco filtra por `move_id.state` (estado de la
  factura): `_get_max_invoice_date()` no distingue si la factura de una
  línea terminó cancelada después de creada la retención — queda fuera de
  alcance de este cambio, no como comportamiento garantizado. (Una
  retención en `cancel` sí puede volver a `write` vía `action_draft`, así
  que no hay inmutabilidad que evite este caso borde; su severidad es baja
  porque requiere cancelar la factura después de haber creado la retención
  draft, y no es el escenario del ticket)

#### Scenario: Fuera de alcance — fecha de factura movida después de emitida la retención

- **GIVEN** una retención `emitted` sobre una factura con
  `invoice_date_display` = `X`
- **WHEN** se modifica `invoice_date_display` de la factura a una fecha
  posterior a la `date_accounting` de la retención
- **THEN** el sistema NO valida esta inconsistencia (los constraints de
  este cambio viven en `account.retention` / `account.retention.line`, no
  en `account.move`) — queda documentado como fuera de alcance, no como
  comportamiento garantizado
