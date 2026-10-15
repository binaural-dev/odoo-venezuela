# Tasks

## 1. Diagnóstico y decisión de diseño

- [x] 1.1 Confirmado que el diferencial cambiario nativo de Odoo
      (`_prepare_exchange_difference_move_vals`/`_create_exchange_difference_moves`,
      core) solo mira `amount_residual` (moneda de compañía) y nunca toca la
      moneda alterna
- [x] 1.2 Evaluado enganchar el cálculo a `foreign_amount_residual`
      (`binaural_account_reports`) y descartado: dependencia circular real
      (ese módulo ya depende de `l10n_ve_accountant`) y no cubre el caso
      "solo hay diferencia en alterno" (su ratio depende de que haya
      conciliación de residual en compañía en el mismo partial)
- [x] 1.3 Verificado leyendo el core (`account/models/account_move_line.py`)
      que `remaining_debit_amount`/`remaining_credit_amount` se zeroan ANTES
      de que cualquier módulo (incluido `l10n_ve_exchange_difference`)
      decida qué documento final construir — confirma que esta feature no
      necesita saber si otro módulo diverge el asiento nativo hacia una nota
      fiscal
- [x] 1.4 Decidido reutilizar `account.partial.reconcile.exchange_move_id`
      (nativo) en vez de una clave de idempotencia propia, para heredar la
      reversión automática de Odoo sin código propio

## 2. Implementación (`l10n_ve_accountant`)

- [x] 2.1 `res_company.py`: toggle `l10n_ve_use_foreign_exchange_diff` +
      `@api.constrains` que exige las cuentas/diario nativos de diferencial
      cambiario
- [x] 2.2 `res_config_settings.py` + `views/res_config_settings_views.xml`:
      exponer el toggle en Ajustes > Contabilidad
- [x] 2.3 `account_move.py`: campos de trazabilidad
      `l10n_ve_exchange_foreign_diff_entry` (con `copy=True`, para que la
      reversión conserve el flag), `l10n_ve_exchange_foreign_source_move_id`,
      `l10n_ve_exchange_foreign_payment_move_id`
- [x] 2.4 `account_move_line.py`: override de
      `_prepare_reconciliation_single_partial` — honra
      `no_exchange_difference`/`no_exchange_difference_no_recursive`, elige
      el lado factura como `rate_source` (con fallback por fecha si ninguno
      de los dos es factura), y reusa el `date` que el propio core calculó
      para su asiento (o `max(debit.date, credit.date)` si el core no
      construyó ninguno) — nunca `fields.Date.context_today()`
- [x] 2.5 `_compute_foreign_exchange_amount`: fórmula
      `base_amount × (tasa_original − tasa_actual)`, con
      `with_company(company)` en `compute_rate` para multi-compañía
- [x] 2.6 `_inject_foreign_exchange_amounts`: deriva el monto base del
      `debit`/`credit` que el core ya calculó para la pareja de líneas (rama
      `amount_residual`), con fallback a `amount_currency` (rama
      `amount_residual_currency`) — nunca re-deriva el monto de forma
      independiente
- [x] 2.7 `_get_settled_company_amount` +
      `_queue_standalone_foreign_exchange_difference`: rama para cuando el
      core no construyó ningún asiento — el antes/después del residual solo
      se usa aquí, donde no hay ambigüedad de a qué lado atribuirlo
- [x] 2.8 `_create_exchange_difference_moves`: corre `super()` primero
      (asientos nativos, ya con el monto alterno inyectado), luego vacía la
      cola de standalone en un `try/finally` sobre `self.env.cr` (estado de
      cursor, no transaccional — no puede sobrevivir a un rollback de
      savepoint)
- [x] 2.9 `_find_settlement_partial` +
      `_create_standalone_foreign_exchange_difference_entry`: busca el
      partial exacto por pareja de líneas (no solo por movimiento, para no
      confundir cuotas del mismo día), reutiliza `exchange_move_id` si ya
      existe, y lo asigna al crear uno nuevo

## 3. Bug encontrado y corregido durante las pruebas con el usuario

- [x] 3.1 Detectado (revisión manual del usuario sobre Ej.12: factura USD
      pagada en USD, 100 vs 100 exacto en alterno) que el cálculo inyectaba
      un monto alterno ficticio (5,00 USD) basado en el delta de VEF, aunque
      el cruce en USD ya cuadraba exacto
- [x] 3.2 Causa raíz: `_compute_foreign_exchange_amount` no distinguía si la
      línea que fija la tasa (`rate_source`, el lado factura) ya estaba
      denominada en la propia moneda alterna — en ese caso su exposición en
      esa moneda es fija desde el origen y no hay nada que revaluar
- [x] 3.3 Corregido con un guard temprano:
      `if self.currency_id == foreign_currency: return 0.0`
- [x] 3.4 Actualizados los 2 tests que asumían el valor incorrecto como
      esperado (`test_native_and_alternate_case_sets_both_amounts_on_same_move`,
      `test_full_flow_foreign_invoice_multiple_partials_mixed_currencies_squares_natively_and_alternately`)
      para exigir explícitamente `foreign_debit`/`foreign_credit = 0` y
      `l10n_ve_exchange_foreign_diff_entry = False` cuando la factura está
      en la moneda alterna

## 4. Verificación

- [x] 4.1 16 tests en `tests/test_foreign_exchange_diff.py`: cálculo puro
      (revaluación/devaluación, toggle apagado, sin cambio de tasa),
      standalone (monto/estado, idempotencia vía `exchange_move_id`,
      reversión), múltiples cuotas parciales en distintas monedas/fechas,
      factura en moneda extranjera con el flujo completo de 3 cuotas
      mixtas, rama `amount_residual_currency`, contexto de supresión nativo,
      y reversión automática del caso combinado
- [x] 4.2 16/16 tests pasan en sandbox aislado (DB `test_l10n_ve_foreign_diff`,
      addons path separado del checkout real — nunca se tocó el working
      directory principal)
- [x] 4.3 Verificado con dumps reales (factura + pago + asiento de
      diferencial juntos, no solo el asiento de diferencial aislado) para 3
      ejemplos representativos: factura en VEF con standalone, factura en
      USD con caso combinado, factura en USD con 3 cuotas mixtas — entregado
      al usuario en PDF/Markdown
- [ ] 4.4 `openspec validate --changes`

## 5. Traducciones (`i18n/es_VE.po`)

- [x] 5.1 Exportado el `.pot` real del módulo (contra el sandbox aislado, no
      el checkout real) con `odoo i18n export` y diferenciado contra el
      `es_VE.po` existente para ubicar únicamente los `msgid` nuevos
      introducidos por esta feature (etiquetas y ayudas de los campos
      `l10n_ve_use_foreign_exchange_diff`,
      `l10n_ve_exchange_foreign_diff_entry`,
      `l10n_ve_exchange_foreign_source_move_id`,
      `l10n_ve_exchange_foreign_payment_move_id`; el texto del bloque de
      Ajustes; el nombre de línea "Alternate currency exchange difference";
      y los 4 mensajes de error/validación de `res_company.py` y
      `account_move_line.py`)
- [x] 5.2 Traducidos y agregados al final de `i18n/es_VE.po`, sin tocar
      ninguna entrada existente — no se traspasó a otros `msgid` sin
      traducción que ya estaban en el archivo por causas ajenas a esta
      feature
- [x] 5.3 Validado cargando el `.po` actualizado en el sandbox (`-u
      l10n_ve_accountant` con el archivo copiado) sin errores, y
      reconfirmados los 16/16 tests tras el cambio

## 6. Ronda 2 — visibilidad, redondeo y reversión (probado en vivo)

- [x] 6.1 Detectado desfase de 1 centavo entre el diferencial calculado y
      `factura.foreign_debit − pago.foreign_credit` real — causa raíz:
      `_compute_foreign_exchange_amount` recalculaba por tasa en vez de leer
      los montos alternos ya guardados
- [x] 6.2 Reemplazado por `_foreign_exposure_at_residual` (función pura,
      telescópica) + `_compute_alt_exchange_diff_from_settlement`/`_slice` —
      ver `design-notes.md` para el detalle matemático
- [x] 6.3 `open_reconcile_view` (`account_move_line.py`): dominio ampliado
      sobre `account.action_account_moves_all_grouped_matching` para incluir
      la línea de cierre del standalone (solo esa, no la de P&L), buscando
      por `l10n_ve_exchange_foreign_source_move_id`/`payment_move_id`
- [x] 6.4 `_get_all_reconciled_invoice_partials` (`account_move.py`): fila
      sintética para el widget "Pagos", único hook común a core/`l10n_ve_igtf`/
      `l10n_ve_payment_extension` (`_compute_payments_widget_reconciled_info`
      está bloqueado porque `l10n_ve_igtf` lo reimplementa sin `super()`)
- [x] 6.5 `is_exchange=True` en la fila sintética: oculta el botón
      "Unreconcile" inútil, a costa de que el renderer (compartido, no
      tocable) etiquete el monto en moneda de compañía en vez de alterna
- [x] 6.6 `_reverse_moves` (`account_move.py`): invierte `foreign_debit`/
      `foreign_credit` en la reversión — core no los tocaba, dejando la
      reversión sin cancelar el monto alterno original
- [x] 6.7 `account_partial_reconcile.unlink()`: red de seguridad que
      revierte el asiento alterno si el mecanismo nativo no lo hizo (caso
      real: `l10n_ve_igtf.js_remove_outstanding_partial` rompe la
      conciliación por un camino que no siempre dispara la reversión nativa)
- [x] 6.8 Ambas vías de visibilidad (6.3, 6.4) excluyen entradas con
      `reversal_move_ids` seteado — un asiento revertido sigue `posted` por
      diseño y sin este filtro seguía apareciendo en la factura
- [x] 6.9 9 tests nuevos cubriendo 6.2, 6.6, 6.7, 6.8 con aserciones exactas
      (no aproximadas) — 34 tests en este archivo, 244 en la suite completa
      del módulo, todos en verde
- [x] 6.10 Comentarios extensos agregados durante esta ronda recortados a
      ≤4 líneas; detalle completo migrado a `design-notes.md`

## 7. Símbolo de moneda incorrecto en el widget de Pagos (fix frontend)

- [x] 7.1 Detectado: la fila sintética del standalone (6.4/6.5) mostraba
      "Bs.F 0,23" en vez de "$ 0,23" — `is_exchange=True` hace que el
      renderer (compartido, no tocable) etiquete el monto con la moneda de
      compañía sin importar qué moneda le pasemos
- [x] 7.2 Confirmado que no hay forma de resolverlo del lado Python: el
      método que arma esa etiqueta (`_compute_payments_widget_reconciled_info`)
      está bloqueado por la reimplementación de `l10n_ve_igtf` (ver § 6.4)
- [x] 7.3 Resuelto con un parche de frontend (`patch()` de Odoo, mismo
      patrón que ya usa este módulo en `tax_totals.js`, sin tocar ningún
      archivo de core): `static/src/components/payment_field/payment_field.js`,
      extiende `AccountPaymentField.getInfo()`
- [x] 7.4 Sin campos nuevos en `account.move` — `foreign_debit`/
      `foreign_credit`/`foreign_currency_id` ya son campos reales en
      `account.move.line` desde el commit original; el JS los lee directo
      por `orm.searchRead`
- [x] 7.5 Verificado con datos reales en una DB temporal (sin necesidad de
      navegador): misma consulta que hace el JS, confirmado que devuelve el
      monto correcto (0,5) con la moneda alterna correcta (USD) en vez de
      la de compañía (VEF) — ver `design-notes.md` para el detalle
- [x] 7.6 Sin tests automatizados de JS (no hay infraestructura de tests
      frontend en este módulo); validado con `node --check` (sintaxis) y la
      suite Python completa (244 tests, sin cambios ya que no se tocó
      ningún modelo)
