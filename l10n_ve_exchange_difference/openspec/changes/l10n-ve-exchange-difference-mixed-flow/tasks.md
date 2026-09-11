# Tasks

## 1. Exclusión de pagos de retención

- [x] 1.1 Identificado que `l10n_ve_payment_extension._reconcile_all_payments`
      ya reconcilia con `no_exchange_difference=True`, pero esa clave no se
      podía reutilizar (este módulo la reusa para otro propósito)
- [x] 1.2 Agregada clave de contexto propia y explícita
      `l10n_ve_exchange_is_retention_reconcile` en
      `l10n_ve_payment_extension/models/account_retention.py`
- [x] 1.3 `account.move.line.reconcile()` respeta esa clave y delega a
      `super()` sin entrar al motor de ND/NC

## 2. Flujo mixto por cliente

- [x] 2.1 Campo `res.company.l10n_ve_exchange_validate_partner_note`
      + setting en Binaural Settings
- [x] 2.2 Campo `res.partner.l10n_ve_exchange_allow_note` (pestaña Contabilidad)
- [x] 2.3 Campo técnico `res.partner.l10n_ve_exchange_show_allow_note`
      (computed, controla visibilidad según `env.company`)
- [x] 2.4 Método `res.company._l10n_ve_exchange_note_allowed_for_partner()`
- [x] 2.5 Gate consultado en `is_own_invoice_line`
      (`_prepare_exchange_difference_move_vals`, `account_move_line.py`)
- [x] 2.6 Vista de contacto: campo ubicado en pestaña Contabilidad
      (`page[@name='accounting']//group[@name='general']`), no en la
      sección principal del formulario

## 3. Fixes encontrados

- [x] 3.1 `.sudo()` agregado a la búsqueda de diario en
      `_check_l10n_ve_exchange_debit_journal_sequences` (bug de
      `journal_comp_rule` filtrando por `allowed_company_ids`)
- [x] 3.2 Resuelto bloqueo circular: visibilidad de
      `l10n_ve_exchange_debit_note_sequence_id` en el diario ya NO depende
      de `l10n_ve_exchange_use_nd_nc` (solo de `type`/`is_debit`)
- [x] 3.3 `_check_l10n_ve_exchange_use_nd_nc_requires_config` daba falso
      positivo al guardar desde Ajustes con producto y pricelist
      correctamente seleccionados: el `create()` de `res.config.settings`
      invierte cada `related` field en su propio `write()` a `res.company`
      (uno por campo, no atómico), y el del toggle boolean llega antes que
      los otros dos. Fix: el constraint encola la verificación real en
      `cr.precommit` (una vez por compañía) en vez de evaluar en el
      momento

## 4. Traducciones

- [x] 4.1 `i18n/es_VE.po` actualizado con los nuevos campos y textos de vista

## 5. Documentación

- [x] 5.1 `proposal.md`/`tasks.md` de este change
- [x] 5.2 Requirements nuevos agregados al spec raíz
      (`openspec/specs/l10n_ve_exchange_difference/spec.md`)
- [x] 5.3 Delta spec de este change (`specs/exchange-difference-note/spec.md`)

## 6. Pendiente

- [ ] 6.1 Tests: retención excluida, gate por cliente (ambos casos),
      flujo mixto desactivado (regresión)
- [ ] 6.2 Punto 4 de la tarea 81554 (advertencia de período fiscal en ND de
      proveedor) -- fuera de alcance de este módulo, pendiente de ubicar
- [ ] 6.3 Levantar en docker-odoo, actualizar módulos y correr suite completa
- [ ] 6.4 `code-reviewer` antes de abrir PR
