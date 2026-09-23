# Spec delta: retention-lines-match-partner

## ADDED Requirements

### Requirement: Las líneas de una retención estándar deben pertenecer al partner de la retención

El sistema SHALL mantener consistencia entre `account.retention.partner_id`
y el partner de las facturas referenciadas por
`retention_line_ids.move_id`, para toda retención que no sea de
facturación a terceros (`is_third_party_retention = False`):

- Al cambiar `partner_id` en una retención en borrador con líneas
  existentes, las líneas SHALL limpiarse automáticamente
  (`onchange_partner_id`), para IVA, ISLR y municipal por igual.
- El sistema SHALL bloquear con `ValidationError` (vía `@api.constrains`,
  independiente del onchange) el guardado de cualquier retención estándar
  que tenga al menos una línea cuya factura pertenezca a un partner
  distinto al `partner_id` de la retención.

Las retenciones de facturación a terceros
(`is_third_party_retention = True`) quedan excluidas de ambas reglas: en
ese flujo, el partner de la factura difiere del partner de la retención
por diseño.

#### Scenario: Cambiar el partner limpia las líneas ISLR existentes

- **GIVEN** una retención ISLR en borrador con líneas de facturas del
  Partner A
- **WHEN** se cambia `partner_id` a Partner B en el formulario
- **THEN** `retention_line_ids` queda vacío
- **AND** no se lanza ningún error

#### Scenario: Confirmar con línea de otro partner está bloqueado

- **GIVEN** una retención ISLR con `partner_id` = Partner B
- **WHEN** se intenta guardar una línea cuya factura (`move_id`) pertenece
  al Partner A
- **THEN** se lanza `ValidationError`, nombrando el partner esperado y las
  facturas en conflicto
- **AND** el cambio no se persiste

#### Scenario: Retención a terceros con partner de factura distinto (sin bloqueo)

- **GIVEN** una retención con `is_third_party_retention = True`
- **WHEN** sus líneas referencian facturas de un partner distinto al
  `partner_id` de la retención
- **THEN** el sistema NO bloquea el guardado ni limpia las líneas al
  cambiar `partner_id` - solo recalcula los montos de las líneas
  existentes con la retención del nuevo partner
