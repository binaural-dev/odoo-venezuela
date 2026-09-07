# exchange-difference-note (delta)

## ADDED Requirements

### Requirement: Los pagos de retención quedan excluidos del flujo de ND/NC

El sistema SHALL NOT generar ND/NC cuando la conciliación de una factura de
cliente contra un pago corresponde a una retención (ISLR/IVA/Municipal)
gestionada por `l10n_ve_payment_extension`, SIN que este módulo declare
ninguna dependencia (directa ni inversa) hacia ese módulo de retenciones.

La exclusión SHALL coordinarse exclusivamente vía una clave de contexto
explícita y propia (`l10n_ve_exchange_is_retention_reconcile`), nunca vía la
clave nativa genérica `no_exchange_difference`.

#### Scenario: Pago de retención sobre factura de cliente en moneda extranjera

- **GIVEN** una factura de cliente en moneda extranjera con el toggle
  `l10n_ve_exchange_use_nd_nc` activado en la compañía
- **WHEN** se concilia contra un pago de retención
- **THEN** la reconciliación entra con el contexto
  `l10n_ve_exchange_is_retention_reconcile=True`
- **AND** el sistema NO genera ninguna ND/NC de este módulo para ese pago

### Requirement: Un flujo mixto permite decidir por cliente si se emite ND/NC o el asiento nativo

El sistema SHALL ofrecer un toggle de compañía adicional
(`l10n_ve_exchange_validate_partner_note`) que, combinado con
`l10n_ve_exchange_use_nd_nc`, permite decidir el flujo de diferencial
cambiario de forma individual por cliente, vía el campo
`res.partner.l10n_ve_exchange_allow_note` (pestaña Contabilidad).

#### Scenario: Flujo mixto activado, cliente CON permiso de nota

- **GIVEN** ambos toggles activados en la compañía
- **AND** el cliente tiene `l10n_ve_exchange_allow_note = True`
- **WHEN** se concilia su factura contra un pago con diferencial
- **THEN** se emite la ND/NC fiscal real

#### Scenario: Flujo mixto activado, cliente SIN permiso de nota

- **GIVEN** ambos toggles activados en la compañía
- **AND** el cliente tiene `l10n_ve_exchange_allow_note = False` (default)
- **WHEN** se concilia su factura contra un pago con diferencial
- **THEN** NO se emite ninguna ND/NC
- **AND** el diferencial se registra con el asiento genérico nativo de Odoo

#### Scenario: Flujo mixto desactivado (comportamiento sin cambios)

- **GIVEN** `l10n_ve_exchange_use_nd_nc` activado y
  `l10n_ve_exchange_validate_partner_note` desactivado
- **WHEN** se concilia cualquier factura de cliente elegible
- **THEN** se emite la ND/NC fiscal real, sin importar el cliente

## MODIFIED Requirements

### Requirement: La configuración falta-parámetro falla RUIDOSO antes de crear nota

El sistema SHALL validar, al guardar el toggle `l10n_ve_exchange_use_nd_nc` en
la compañía, que exista un diario dedicado de ND (`is_debit=True`,
`type='sale'`) con ambas secuencias configuradas. Esa búsqueda SHALL usar
`sudo()` -- `journal_comp_rule` (núcleo) filtra `account.journal` por las
compañías permitidas del usuario, no por el `company_id` del dominio; sin
`sudo()`, guardar el toggle para una compañía fuera de las permitidas del
usuario actual encontraba el diario vacío en silencio y bloqueaba el guardado
con un error de configuración incorrecto.

La visibilidad del campo `l10n_ve_exchange_debit_note_sequence_id` en el
formulario del diario SHALL depender únicamente de `type`/`is_debit`, NUNCA
del toggle `l10n_ve_exchange_use_nd_nc` de la compañía -- condicionarla a ese
toggle crea un bloqueo circular: el toggle exige que el campo ya esté
configurado para poder activarse, pero el campo permanecía oculto hasta que
el toggle estuviera activo.

#### Scenario: Guardar el toggle sin diario dedicado configurado

- **GIVEN** una compañía sin diario `is_debit=True` de tipo `sale`, o sin su
  secuencia de ND asignada
- **WHEN** se intenta activar `l10n_ve_exchange_use_nd_nc`
- **THEN** el guardado falla con un `ValidationError` claro
- **AND** el campo de secuencia de ND es visible y editable en el diario
  ANTES de activar el toggle (no depende de él)

#### Scenario: Guardar el toggle con diario correctamente configurado, en cualquier compañía permitida del usuario

- **GIVEN** un diario `is_debit=True` de tipo `sale` con ambas secuencias
  (ND y `refund_sequence_id`) configuradas para la compañía que se está
  guardando
- **WHEN** se activa `l10n_ve_exchange_use_nd_nc`, sin importar si esa
  compañía es o no la compañía activa del usuario en el selector
  multi-compañía
- **THEN** el guardado se completa sin error
