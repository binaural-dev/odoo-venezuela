# Fix: retención ISLR permitía confirmar con líneas de facturas de otro partner

## Why

Ticket de helpdesk #15341: **"Retención de ISLR permite confirmar con
líneas de facturas de un cliente/proveedor distinto al seleccionado"**.

`onchange_partner_id()` (`account.retention`) solo recargaba/limpiaba
`retention_line_ids` cuando `type_retention == "iva"` - así desde el
commit que introdujo el método en 17.0 (confirmado con
`git log -L` sobre el método). Para retenciones ISLR y municipales no
pasaba nada al cambiar el partner: las líneas ya agregadas seguían
apuntando a facturas del partner anterior, sin que la UI las limpiara ni
existiera ninguna validación de servidor que bloqueara guardar o
confirmar ese estado inconsistente (create/write directo, importación,
etc. - cualquier vía que no pasara por el onchange de la vista).

## What Changes

- `l10n_ve_payment_extension/models/account_retention.py`
  - `onchange_partner_id()`: reescrito a un solo loop que despacha por
    tipo de retención - retenciones a terceros recalculan montos sin
    reemplazar líneas (comportamiento sin cambios), IVA sigue
    recargando/reemplazando líneas (comportamiento sin cambios), y ahora
    ISLR/municipal **limpian** las líneas existentes (`clear_retention()`)
    cuando cambia el partner, en vez de dejarlas intactas.
  - Nueva `@api.constrains("partner_id", "retention_line_ids",
    "is_third_party_retention") _check_lines_match_partner()`: bloquea
    guardar una retención estándar (no a terceros) si alguna línea
    pertenece a una factura (`move_id.partner_id`) distinta al
    `partner_id` de la retención. Es un guard de servidor, independiente
    del onchange - cubre cualquier camino que deje el registro en ese
    estado, no solo la edición manual en el formulario.
  - Incidental: se retiran 6 usos de `states={"draft": [("readonly",
    False)]}` en campos de `account.retention` (`name`, `code`,
    `partner_id`, `date`, `date_accounting`, `retention_line_ids`). Ese
    parámetro ya no existe en el ORM de esta versión de Odoo (se reporta
    como "unknown parameter 'states'" en cada carga del módulo) y no
    tenía ningún efecto; el `readonly` real ya está resuelto en las
    vistas (`readonly="state in [...]"`).
- `l10n_ve_payment_extension/tests/test_retention_islr_partner_change.py`
  (nuevo)
  - `test_islr_lines_cleared_when_partner_changes`: cambiar el partner en
    el formulario ISLR limpia las líneas existentes.
  - `test_mismatched_partner_lines_blocked_on_save`: crear directamente
    (sin pasar por el onchange) una retención ISLR con una línea de un
    partner distinto lanza `ValidationError`.

## Impact

- **Capability**: `retention-lines-match-partner` (nueva).
- **Módulo**: `l10n_ve_payment_extension`.
- **Alcance**: aplica a los tres `type_retention` (`iva` sin cambios,
  `islr`/`municipal` corregidos) para retenciones estándar; las
  retenciones a terceros (`is_third_party_retention`) quedan
  explícitamente excluidas de la nueva constraint, porque en ese flujo el
  partner de la factura difiere del partner de la retención por diseño.
- **Riesgo**: bajo-medio. El refactor de `onchange_partner_id` preserva
  el comportamiento observable para los casos ya cubiertos (verificado
  corriendo la suite completa del módulo, 427→432 tests, antes y después
  del refactor). La nueva constraint es aditiva (nunca bloqueaba nada
  antes) y excluye explícitamente el único flujo legítimo con partners
  distintos.
- **Verificado**: tests dirigidos y suite completa del módulo corridos en
  contenedor Docker sobre bases de datos limpias; sin fallos.
