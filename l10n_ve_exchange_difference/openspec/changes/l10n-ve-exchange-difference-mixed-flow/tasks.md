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

- [x] 6.1 Tests: retención excluida, gate por cliente (ambos casos),
      flujo mixto desactivado (regresión) -- `test_exchange_note_mixed_flow.py`
- [x] 6.2 Punto 4 de la tarea 81554 (advertencia de período fiscal en ND de
      proveedor) -- implementado en `l10n_ve_invoice`/`account_debit_note.py`,
      reutilizando `account.move._get_period_limit` (quincena de
      contribuyente especial) en vez de comparar mes/año calendario; tests
      en `l10n_ve_invoice/tests/test_debit_note_fiscal_period_warning.py`
- [x] 6.3 Levantado en docker-odoo, módulos actualizados y suite completa
      corrida (`l10n_ve_exchange_difference`, `l10n_ve_invoice`,
      `l10n_ve_accountant`) -- 0 fallas atribuibles a este change
- [ ] 6.4 `code-reviewer` antes de abrir PR

## 7. Encontrado durante el seguimiento (revisión de `pastor-binaural`)

- [x] 7.1 `res.partner.l10n_ve_exchange_allow_note` marcado
      `company_dependent=True` -- el toggle que lo gobierna vive en
      `res.company`, así que el permiso del cliente no puede ser único
      para toda la base en multi-compañía
- [x] 7.2 Fecha de Tasa (`invoice_date`) de la ND: acotada primero solo a
      compras, pero eso dejaba una inconsistencia real en documentos de
      venta según si el formulario se abría/editaba antes de guardar
      (`l10n_ve_accountant._onchange_invoice_date_display` la
      re-derivaba). Fix definitivo: ese `onchange` ahora respeta
      `debit_origin_id`/`reversed_entry_id` -- la Fecha de Tasa del origen
      se mantiene para CUALQUIER Nota, venta o compra
- [x] 7.3 Test que ejercita el método real
      `_check_l10n_ve_exchange_debit_journal_sequences` (no solo su query
      interna) para justificar el `.sudo()` de 3.1
