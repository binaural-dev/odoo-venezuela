# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el desfase reportado (300 USD → 300,57) y trazado hasta
      la convivencia de dos vías de conversión: multiplicar por
      `foreign_inverse_rate` vs. `_convert()`
- [x] 1.2 Identificada la causa raíz: la migración v17 (base USD) → v19
      (base VEF) intercambió el significado de `foreign_rate` y
      `foreign_inverse_rate` en `compute_rate`
- [x] 1.3 Inventariados los 8 sitios productivos que multiplican por una tasa
      en los tres repos, clasificados por dirección correcta / invertida /
      rama muerta
- [x] 1.4 Verificado en instancia que `compute_all` sigue vigente en el core
      de v19 (42 llamadas, sin marca de deprecación) y que el core hace la
      misma separación entre motor nuevo y `compute_all`
- [x] 1.5 Medido el impacto del redondeo: ida y vuelta exacto (error 0) con
      `round=False` + `float_round`; y 13,79% de desvío con impuesto incluido
      en precio si no se usa `compute_all`
- [x] 1.6 Confirmado que `tax_totals` ya trae el monto alterno correcto en una
      tercera moneda (PO en EUR: 110,01 por ambas vías)

## 2. `l10n_ve_accountant`

- [x] 2.1 `_get_foreign_rate_date()` como única fuente de fecha de la línea
- [x] 2.2 `_compute_foreign_price`: `_convert(round=False)` + `float_round` a
      "Foreign Product Price", guard de moneda alterna ausente
- [x] 2.3 `_compute_price_unit_ves`: `_convert()` en lugar de dividir entre
      `currency_id.rate` (elimina además un `ZeroDivisionError` latente)
- [x] 2.4 `_get_non_invoice_foreign_value`: usa el helper de fecha
- [x] 2.5 `@api.depends` completados con `currency_id`, `move_id.invoice_date`
      y `move_id.date` en los tres computes afectados
- [x] 2.6 `_compute_foreign_taxable_income`: acceso con `.get(..., 0)`
- [x] 2.7 `_compute_foreign_total_billed`: se lee de `tax_totals`, sin la rama
      que reconvertía en tercera moneda
- [x] 2.8 `_compute_foreign_subtotal` ya usaba `compute_all` desde v16: sin
      cambios

## 3. `l10n_ve_sale`

- [x] 3.1 `foreign_rate_date`: campo nuevo, oculto en el formulario, con
      `default` propio (el ORM no ejecuta `_compute_rate` en `create` porque
      `foreign_rate` ya trae `default`)
- [x] 3.2 `_compute_rate` sella la fecha también en las ramas donde hace
      `continue`, para que la tasa congelada conserve su fecha
- [x] 3.3 `sale.order.line._compute_foreign_price`: usa `foreign_rate_date`,
      con `round=False` + `float_round`, y ramas duplicadas fusionadas
- [x] 3.4 `_compute_foreign_subtotal`: pasa por `compute_all`
- [x] 3.5 `_prepare_invoice`: pasa `foreign_rate_date` como `invoice_date`
- [x] 3.6 `_compute_amount_signed` y los totales alternos: se leen de
      `tax_totals`
- [x] 3.7 Corregido el doble `@api.depends` en `_compute_foreign_total_billed`,
      que anulaba las dependencias reales dejando solo `tax_totals`
- [x] 3.8 Multi-compañía: las decisiones se toman con `company_id` de la
      orden, no con `env.company`
- [x] 3.9 Eliminado `_update_invoices_rate`: código muerto, sin invocadores en
      ningún repo
- [x] 3.10 Migración `19.0.1.0.6/post-set_foreign_rate_date.py` para las
      órdenes existentes no facturadas

## 4. `binaural_purchase` (integra-addons, sin openspec)

- [x] 4.1 `_compute_foreign_price`: `round=False` + `float_round`, guard de
      `currency_id` vacío, ramas duplicadas fusionadas
- [x] 4.2 `_compute_foreign_subtotal`: pasa por `compute_all`
- [x] 4.3 `_compute_tax_totals`: restaurada la inyección de
      `active_id`/`active_model`, como en `account.move` y `sale.order`
- [x] 4.4 Totales alternos y `_compute_amount_signed`: desde `tax_totals`
- [x] 4.5 El onchange deja de forzar `foreign_price`: lo recalcula el compute
- [x] 4.6 Limpieza: dos tests renombrados (el nombre afirmaba lo contrario de
      lo que verificaban), test de traducciones eliminado, `.po` con salto de
      línea final, contenedor de la vista renombrado

## 5. Verificación

- [x] 5.1 `l10n_ve_accountant`: 32 tests, 0 fallos
- [x] 5.2 `l10n_ve_sale`: 20 tests, 0 fallos
- [x] 5.3 `binaural_purchase`: 43 tests, 0 fallos
- [x] 5.4 16 tests nuevos, cada uno construido para fallar si se revierte el
      cambio que verifica
- [ ] 5.5 Validación funcional contra el ejemplo del ticket (Bs 6.215,30 /
      12.430,60 / total 21.629,24) — pendiente, la tarea está en
      "Validación - BIN"
- [ ] 5.6 `openspec validate --changes`

## 6. Fuera de alcance, inventariado aparte

- [ ] 6.1 Dirección de conversión invertida en `binaural_hr_payroll`
      (`get_vef_wage` devuelve USD y sale impreso en cuatro plantillas de
      recibo)
- [ ] 6.2 Doble multiplicación por la tasa en
      `binaural_advance_payment_igtf` sobre la base imponible de IGTF
- [ ] 6.3 Impresión fiscal: `l10n_ve_account_mf`, `binaural_ft`,
      `binaural_club_socios_mf` — requieren notificación previa
- [ ] 6.4 Limpieza de restos v17: montos alternos de retención, ramas muertas
      de `l10n_ve_invoice_digital`, `l10n_ve_iot_mf` marcado como no
      instalable, y `legacy_compute_line_ids_foreign_debit_and_credit` con su
      `TypeError` y su acción de servidor
