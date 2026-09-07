# Feat: Flujo mixto de diferencial cambiario por cliente + exclusión de retenciones

## Why

Ref. tarea Binaural: https://binaural.odoo.com/odoo/action-341/81554
("Flujo Mixto de Diferencia en cambio").

Con el módulo `l10n_ve_exchange_difference` ya en producción, surgieron dos
necesidades adicionales:

1. Algunos clientes negocian con la empresa que su diferencial cambiario se
   siga documentando con el asiento nativo de Odoo, no con una ND/NC fiscal
   -- pero el toggle existente (`l10n_ve_exchange_use_nd_nc`) es todo-o-nada
   a nivel de compañía: no permite convivir ambos flujos según el cliente.
2. Los pagos de retención (ISLR/IVA/Municipal, gestionados por
   `l10n_ve_payment_extension`) estaban entrando por error al mismo motor de
   ND/NC, generando notas fiscales espurias sobre una conciliación que no es
   una factura pagada por el cliente en el sentido que este módulo espera.

## What Changes

**Exclusión de pagos de retención (sin dependencia dura):**
`account.move.line.reconcile()` ahora respeta una clave de contexto
EXPLÍCITA y propia (`l10n_ve_exchange_is_retention_reconcile`), que
`l10n_ve_payment_extension` setea al conciliar una retención
(`account_retention.py::_reconcile_all_payments`). Se descartó usar la clave
nativa genérica `no_exchange_difference` (que ya está presente en ese mismo
punto) porque este propio módulo la reutiliza para otro propósito (cerrar la
línea por cobrar de su propia ND/NC) -- leerla habría confundido ambos casos.
Cero dependencia en ningún sentido entre los dos módulos: coordinación pura
por convención de contexto.

**Flujo mixto por cliente:**

| Modelo | Campo | Tipo | Descripción |
|--------|-------|------|-------------|
| `res.company` | `l10n_ve_exchange_validate_partner_note` | Boolean | Activa la validación por cliente (Binaural Settings) |
| `res.partner` | `l10n_ve_exchange_allow_note` | Boolean | Permiso de ND/NC del cliente (pestaña Contabilidad) |
| `res.partner` | `l10n_ve_exchange_show_allow_note` | Boolean (computed, no store) | Técnico: controla la visibilidad del campo anterior según `env.company` |

Nuevo método `res.company._l10n_ve_exchange_note_allowed_for_partner(partner)`,
consultado desde el gate `is_own_invoice_line` de
`_prepare_exchange_difference_move_vals` (`account_move_line.py`). Con el
toggle de compañía desactivado (default), el comportamiento es idéntico al de
antes de esta feature.

**Fixes encontrados durante la implementación:**

- `res_company.py::_check_l10n_ve_exchange_debit_journal_sequences` no tenía
  `.sudo()` en su búsqueda de diario, a diferencia de todas las búsquedas
  equivalentes del módulo -- `journal_comp_rule` (núcleo) podía devolver vacío
  en silencio y bloquear el guardado del toggle con un `ValidationError`
  incorrecto ("diario no configurado") aunque el diario sí lo estuviera.
- Bloqueo circular real en la UI del diario: el campo
  `l10n_ve_exchange_debit_note_sequence_id` solo era visible cuando
  `company_id.l10n_ve_exchange_use_nd_nc` ya estaba activo, pero ese mismo
  toggle exige (constraint) que el campo ya esté configurado para poder
  activarse -- imposible de configurar desde cero. Se quitó esa condición de
  la visibilidad del campo (ahora depende solo de `type`/`is_debit`).

## Impact

- **Capability**: `exchange-difference-note` (extendida, no nueva).
- **Módulos**: `l10n_ve_exchange_difference` (campos/lógica nuevos, 2 fixes),
  `l10n_ve_payment_extension` (contexto explícito agregado en
  `_reconcile_all_payments`).
- **Fuera de alcance de este change**: advertencia de período fiscal en Notas
  de Débito de PROVEEDOR (punto 4 de la tarea 81554) -- no vive en este
  módulo (que es exclusivo de facturas de CLIENTE); pendiente de ubicar en
  el módulo correcto (`l10n_ve_invoice`/`account_debit_note`) antes de
  implementarse.
- **Tests existentes**: sin cambios de comportamiento con ambos toggles
  nuevos desactivados (default) -- no deberían romperse.
- **Tests nuevos**: pendientes (retención excluida, gate por cliente activado/
  desactivado, ambos escenarios de flujo mixto).
