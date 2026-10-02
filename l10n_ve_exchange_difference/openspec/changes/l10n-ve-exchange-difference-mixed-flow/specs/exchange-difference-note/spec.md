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

### Requirement: El selector del Producto de Nota de Diferencial solo ofrece candidatos compatibles

El `domain` de `res.company.l10n_ve_exchange_note_product_id` SHALL restringir
el selector a productos de tipo Servicio cuyo impuesto de venta sea el exento
por defecto (`exent_aliquot_sale`) Y cuyo impuesto de compra sea el exento
por defecto (`exent_aliquot_purchase`), ambos de `l10n_ve_accountant`. Si
cualquiera de los dos impuestos exentos no está configurado en la compañía,
el selector SHALL NOT ofrecer ningún producto.

El selector real que ve el usuario es
`res.config.settings.l10n_ve_exchange_note_product_id` (Ajustes > Binaural
Settings), un `related='company_id...'`. Ese campo SHALL declarar el mismo
`domain` string de forma explícita e idéntica a la de `res.company` -- en
Odoo 19 un related NO hereda un `domain` de tipo string de su campo de
origen (`_related_domain`, `odoo/orm/fields_relational.py`, lo descarta
salvo que el campo sea `inherited`); sin esa declaración explícita, el
selector de Ajustes queda sin ningún filtro.

Esta restricción es solo de UI (el `domain` está declarado como string,
evaluado únicamente del lado del cliente web) -- no reemplaza la validación
real de `_check_l10n_ve_exchange_note_product_id`, que sigue aplicando sobre
cualquier valor asignado por otra vía (ORM directo, API).

#### Scenario: Ambos impuestos exentos configurados

- **GIVEN** la compañía tiene `exent_aliquot_sale` y `exent_aliquot_purchase` configurados
- **WHEN** se abre el selector de `l10n_ve_exchange_note_product_id` (Ajustes o `res.company`)
- **THEN** solo aparecen productos de tipo Servicio con AMBOS impuestos asignados

#### Scenario: Falta uno de los dos impuestos exentos

- **GIVEN** la compañía NO tiene `exent_aliquot_purchase` configurado (o le falta `exent_aliquot_sale`)
- **WHEN** se abre el selector de `l10n_ve_exchange_note_product_id` (Ajustes o `res.company`)
- **THEN** el selector no ofrece ningún producto, sin importar cuántos productos de tipo Servicio existan

#### Scenario: El domain de res.config.settings no depende de la propagación automática

- **GIVEN** el `domain` de `res.company.l10n_ve_exchange_note_product_id`
- **WHEN** se compara contra el `domain` de `res.config.settings.l10n_ve_exchange_note_product_id`
- **THEN** ambos son idénticos -- el related declara su propio string explícito

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
