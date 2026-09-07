# Tasks

## 1. Diseño de arquitectura

- [x] 1.1 Decidido generar la ND vía `account.debit.note` (wizard nativo de
      `account_debit_note`) en vez de construir el asiento a mano
- [x] 1.2 Decidido 100% opt-in por compañía (`igtf_note_debit_mode`), todos
      los métodos sobrescritos delegan en `super()` para el modo `inline`
- [x] 1.3 Decidido usar `origin_payment_to_pay_igtf` para vincular la ND al
      pago de origen (en vez de un contexto o tabla intermedia)

## 2. Implementación de core

- [x] 2.1 Creado modelo `res.company` con configuración (modo, producto,
      diario VEF, checkbox por defecto, computados de dominio)
- [x] 2.2 Creado `res.config.settings` con related/inverse
- [x] 2.3 Implementado `prepare_igtf_payment_debit_note` (genera la ND)
- [x] 2.4 Implementado `settle_igtf_debit_note` +
      `_settle_igtf_debit_note_with_vef_payment` (cobro de la ND)
- [x] 2.5 Sobrescrito `js_assign_outstanding_line` (conciliación manual,
      separa base/IGTF sin asiento intermedio)
- [x] 2.6 Sobrescrito `_create_advance_payment_move` (cruce de anticipo sin
      línea embebida)
- [x] 2.7 Sobrescrito `_create_igtf_moves_in_payments` (no embebe línea)
- [x] 2.8 Sobrescrito `compute_bi_igtf` (base imponible/IGTF en la factura)
- [x] 2.9 Implementado `create_note_credit_igtf` +
      `_unreconcile_and_cancel_advance` (reversa)
- [x] 2.10 Sobrescrito `remove_igtf_from_account_move` (dispara la reversa)

## 3. Wizard de registro de pago

- [x] 3.1 Campo `igtf_note_debit_include_in_payment` (checkbox)
- [x] 3.2 Sobrescrito `_compute_amount` (ajusta monto si el checkbox está
      desmarcado)
- [x] 3.3 Sobrescrito `_onchange_amount` (bandera interna para no corromper
      `custom_user_amount`)
- [x] 3.4 Sobrescrito `_compute_payment_difference`
- [x] 3.5 Campo `total_amount_with_igtf_note_debit` (desglose Importe + IGTF)
- [x] 3.6 Implementado `_check_igtf_note_debit_group_payment` (bloqueo de
      pagos agrupados multi-factura)
- [x] 3.7 Sobrescrito `_create_payments` (genera y concilia la ND tras crear
      el/los pagos)

## 4. Vistas

- [x] 4.1 `views/res_config_settings_views.xml` (configuración)
- [x] 4.2 `wizard/account_payment_register_views.xml` (checkbox + desglose)
- [x] 4.3 `views/account_move_views.xml` (indicador de ND pendiente)

## 5. Bugs reales encontrados y corregidos

- [x] 5.1 **Conversión de moneda con pago no indexado**: `_create_payments`
      usaba siempre `payment.date` para convertir `igtf_amount` a moneda de
      compañía, ignorando `indexed_default`. Corregido: la fecha de
      conversión sigue la misma regla que el cálculo base
      (`payment.date` si indexado, `invoice.invoice_date` si no)
- [x] 5.2 **Onchange duplicado**: `_onchange_amount` con
      `igtf_note_debit_include_in_payment` como trigger causaba doble
      invocación en el mismo ciclo de onchange, corrompiendo
      `custom_user_amount`. Corregido quitando el trigger redundante
- [x] 5.3 Code review previo (5 hallazgos): módulo no 100% opt-in (duplicaba
      lógica en vez de usar `super()`), reversa solo ventas, tolerancia de
      conciliación invertida, `@api.depends` incompletos -- todos corregidos

## 6. Tests

- [x] 6.1 `test_igtf_note_debit_config.py` (validaciones de configuración)
- [x] 6.2 `test_igtf_note_debit_unit.py` (unitarios de los métodos nuevos)
- [x] 6.3 `test_igtf_note_debit_service.py` (flujo de servicio completo)
- [x] 6.4 `test_igtf_note_debit_wizard.py` (wizard de registro de pago)
- [x] 6.5 `test_igtf_note_debit_advance_payment.py` (cruce de anticipo)
- [x] 6.6 `test_igtf_note_debit_multicurrency.py` (pago/factura en monedas
      distintas, `indexed_default`)
- [x] 6.7 244 tests verdes entre `l10n_ve_igtf`, `l10n_ve_igtf_note_debit` y
      `l10n_ve_exchange_difference`

## 7. Documentación

- [x] 7.1 README.rst (flujo completo, configuración, indicadores)
- [x] 7.2 readme/DESCRIPTION.rst (resumen para el manifest)
- [x] 7.3 Docstrings y comentarios en código sobre puntos delicados
      (bandera interna del wizard, `.sudo()` en `compute_bi_igtf`,
      `indexed_default`)
- [x] 7.4 i18n: `i18n/es_VE.po` + `i18n/l10n_ve_igtf_note_debit.pot`
      actualizados con todos los strings traducibles

## 8. OpenSpec

- [x] 8.1 `config.yaml` generado
- [x] 8.2 `proposal.md` generado (Why, What Changes, historial de bugs, Impact, Limitaciones)
- [x] 8.3 `spec.md` generado (7 requirements con scenarios Given/When/Then)
- [x] 8.4 `tasks.md` generado (este archivo)
- [x] 8.5 Spec global agregada en `openspec/specs/l10n_ve_igtf_note_debit/spec.md`

## 9. Pendiente: Code review formal antes de merge

- [ ] 9.1 Validar que todos los requirements de spec.md están implementados
- [ ] 9.2 Verificar que ningún texto en proposal/spec contradice código
- [ ] 9.3 Ejecutar `openspec validate --changes`
- [ ] 9.4 Aprobación de stakeholder
