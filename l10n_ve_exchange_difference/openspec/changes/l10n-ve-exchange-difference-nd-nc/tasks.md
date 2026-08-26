# Tasks

## 1. Diseño de arquitectura

- [x] 1.1 Decidido interceptar hook nativo `_prepare_exchange_difference_move_vals`
      en lugar de reemplazar el motor completo (menor riesgo, máxima reutilización)
- [x] 1.2 Verificado que Odoo NO cancela ni rechaza tener múltiples asientos de
      diferencial por partial (un para el genérico, otro para la ND/NC)
- [x] 1.3 Decidido usar stash en `self.env.cr` para pasar estado entre métodos
      (alternativa a `context`, evita contaminación a sibling calls)
- [x] 1.4 Identificado punto de creación: `_create_exchange_difference_moves()`,
      justo DESPUÉS de que Odoo crea los partials reales, ANTES de full-reconcile

## 2. Implementación de core

- [x] 2.1 Creado modelo `account.move` con campos nuevos
      (`l10n_ve_exchange_diff_entry`, `l10n_ve_exchange_original_id`, etc.)
- [x] 2.2 Creado modelo `res.company` con configuración obligatoria
      (producto, pricelist, toggle)
- [x] 2.3 Sobrescrito `account.move.line.reconcile()` con filtrado de líneas elegibles
- [x] 2.4 Sobrescrito `_prepare_exchange_difference_move_vals()` con encolamiento
- [x] 2.5 Sobrescrito `_create_exchange_difference_moves()` con creación de ND/NC
- [x] 2.6 **[RIESGOSO]** Sobrescrito `_prepare_reconciliation_single_partial()`
      (MÉTODO INTERNO, acoplamiento a Odoo 19.0-20260710)
- [x] 2.7 Implementado `_create_exchange_difference_note()` (creación de ND/NC)
- [x] 2.8 Implementado `_reverse_exchange_note()` (reversión sin cancelación)
- [x] 2.9 Sobrescrito `js_remove_outstanding_partial()` (triggerear reversión)
- [x] 2.10 Sobrescrito `_reverse_moves()` (vincular reversals vía
       `l10n_ve_exchange_original_id`)

## 3. Configuración y validaciones

- [x] 3.1 Constraint `_check_l10n_ve_exchange_use_nd_nc_requires_config` en
      `res.company` (fuerza product + pricelist al activar toggle)
- [x] 3.2 Constraint `_check_l10n_ve_exchange_note_pricelist_id` (pricelist
      debe estar en moneda de compañía)
- [x] 3.3 Constraint `_check_l10n_ve_exchange_note_product_id` (producto debe
      ser servicio con cuentas de ganancia/pérdida correctas + impuesto exento)
- [x] 3.4 UserError en tiempo de reconciliación si falta diario dedicado de ND
      o su secuencia (defensa en profundidad)
- [x] 3.5 Guard anti-duplicado con `reversal_move_ids` (excluye notas revertidas)

## 4. Pagos agrupados (attribution correcta)

- [x] 4.1 Implementado stash de pareja real (debit_values['aml'],
      credit_values['aml']) en `_prepare_reconciliation_single_partial()`
- [x] 4.2 Implementado consumo del stash en `_prepare_exchange_difference_move_vals()`
      para derivar factura EXACTA (no por orden)
- [x] 4.3 Test `test_grouped_payment_gain_direction_invoice_attribution_limitation`
      con dos facturas de montos DISTINTOS (100 vs 500 USD) para detectar swaps

## 5. Gestión de recursión

- [x] 5.1 Context cleanup antes de crear nota (remover `skip_invoice_sync`,
      `active_id`, `active_model`, contexto de IDs)
- [x] 5.2 Uso de `_disable_recursion()` con `target=False` para desbloquear
      sync de líneas dinámicas de la nota
- [x] 5.3 Uso de `no_exchange_difference=True` al cerrar nota contra residual
      (evita recursión en el motor de diferencial)
- [x] 5.4 Guard: si `note_line` (receivable) queda vacío, falla con UserError
      en lugar de silenciosamente orfanar la ND

## 6. Secuencia de ND dedicada

- [x] 6.1 Agregado campo `l10n_ve_exchange_debit_note_sequence_id` a `account.journal`
- [x] 6.2 Vista solo expone el campo cuando `type='sale'` AND `is_debit=True`
- [x] 6.3 Sobrescrito `_compute_name_by_sequence()` para usar secuencia dedicada
- [x] 6.4 Sobrescrito `_sequence_matches_date()` para saltar validación
      (secuencia de ND es ajena al diario)

## 7. Tests y cobertura

- [x] 7.1 Base de 47 tests (crecer desde 36 test iniciales)
- [x] 7.2 Test de compatibilidad Odoo: `test_odoo_core_api_compatibility`
- [x] 7.3 Test básico de flujo: `test_exchange_difference_settled_by_real_note_via_register_payment`
- [x] 7.4 Test de reversión: `test_exchange_note_reversed_on_unreconcile`
- [x] 7.5 Test anti-duplicado: `test_reconciling_again_after_reversal_generates_new_note`
- [x] 7.6 Test de pagos agrupados: `test_grouped_payment_gain_direction_invoice_attribution_limitation`
- [x] 7.7 Test de NC reversal: `test_exchange_note_debit_note_reversed_on_unreconcile`
- [x] 7.8 Test de bloqueo directo: `test_exchange_note_own_reconciliation_cannot_be_broken_directly`
- [x] 7.9 Tests de validaciones (producto, pricelist, diario)
- [x] 7.10 Tests de fallback (proveedor, misceláneo -- sin ND/NC propia)
- [x] 7.11 Tests de IGTF: `test_exchange_note_debit_note_with_igtf_attributes_each_note_to_its_own_invoice`
- [x] 7.12 Cobertura alcanzada: 98% en l10n_ve_exchange_difference

## 8. Cambios en módulos vecinos (RecursionError + perf)

- [x] 8.1 l10n_ve_accountant/models/account_move.py: Remover `with_context()`
      por registro en `_compute_tax_totals()`, delegar directo (RecursionError fix)
- [x] 8.2 l10n_ve_accountant/models/account_tax.py: Cambiar `active_model ==` a
      `record._name ==` (robustez)
- [x] 8.3 l10n_ve_igtf/models/account_move.py: Reemplazar
      `reconciled_lines_ids.mapped()` por `matched_debit_ids | matched_credit_ids`
      (evita Many2many computado)

## 9. Fixtures de test corregidas (bug de composición de tasas)

- [x] 9.1 l10n_ve_igtf/tests/test_igtf_common_partner_formal_VEF.py:
      Agregar `'rate': 1/380.0000` explícito en segunda entrada
- [x] 9.2 l10n_ve_igtf/tests/test_common_sale_book_igtf_usd_partner_formal.py:
      Agregar `'rate': 1/380.0000` explícito
- [x] 9.3 l10n_ve_igtf/tests/test_common_purchase_book_igtf_usd_provider_formal.py:
      Agregar `'rate': 1/380.0000` explícito
- [x] 9.4 Comentarios explicativos del bug de `_sanitize_vals()` +
      `_inverse_company_rate()` agregados a los 3 archivos

## 10. Documentación

- [x] 10.1 README.rst escrito (flujo, configuración, limitaciones)
- [x] 10.2 index.html con diagrama SVG del flujo
- [x] 10.3 Docstrings en Python (métodos y campos)
- [x] 10.4 Comentarios en código sobre puntos delicados (recursión, stash, API interna)
- [x] 10.5 __manifest__.py con descripción y dependencias

## 11. Mitigación de riesgo de API interna

- [x] 11.1 Test `test_odoo_core_api_compatibility` en test suite (verificar
       firma de `_prepare_reconciliation_single_partial`)
- [x] 11.2 Runtime guard en `_prepare_reconciliation_single_partial` (verificar
       que 'aml' keys existan, falla con RuntimeError si no)
- [x] 11.3 Documentado en código: "Verified against Odoo 19.0-20260710"
- [x] 11.4 Commit agregado con mitigación (cce048db5)

## 12. Verificación cruzada de módulos

- [x] 12.1 Identificados módulos que sobrescriben puntos de enganche:
        `od_journal_sequence`, `l10n_ve_donation`, `l10n_ve_payment_extension`,
        `binaural_subsidiary`, `binaural_advance_payment_igtf`, `binaural_account_reports`
- [x] 12.2 Verificado que todos delegan a `super()` correctamente
- [x] 12.3 Ejecutados tests multi-módulo: 269 tests verde (l10n_ve_accountant +
        l10n_ve_invoice + l10n_ve_igtf + account_invoice_pricelist +
        l10n_ve_exchange_difference)

## 13. Pendiente: OpenSpec

- [x] 13.1 config.yaml generado
- [x] 13.2 proposal.md generado (Why, What Changes, Impact, Limitaciones, Hallazgos)
- [x] 13.3 spec.md generado (9 requirements con scenarios en formato Given/When/Then)
- [x] 13.4 tasks.md generado (este archivo)

## 14. Pendiente: Code review formales antes de merge

- [ ] 14.1 Validar que todos los requirements de spec.md están implementados
- [ ] 14.2 Verificar que ningún texto en proposal/spec contradice código
- [ ] 14.3 Ejecutar `openspec validate --changes`
- [ ] 14.4 Aprobación de stakeholder
