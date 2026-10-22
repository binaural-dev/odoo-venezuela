# Tasks

## 1. Diagnóstico

- [x] 1.1 Confirmado que las columnas y totales foreign de las vistas de
      retención son invisibles con base VEF
- [x] 1.2 Confirmado que las ramas de reportes que leen `foreign_*` no corren
      con base VEF (ARC-V ya retirado)
- [x] 1.3 Confirmado que `legacy_compute_line_ids_foreign_debit_and_credit`
      (único lector de `payment.retention_foreign_amount`) no tiene llamadores
- [x] 1.4 Confirmado que el USD del asiento sale de `_get_foreign_value` /
      `_get_non_invoice_foreign_value`, no de los `foreign_*` de la línea
- [x] 1.5 Identificado `binaural_mobile` como consumidor externo que debe
      dejar de usarlos
- [ ] 1.6 Verificar con una prueba que, sin la rama que fuerza la tasa de la
      factura (`_get_foreign_rate_date` de `account_move_line.py` y
      `_synchronize_to_moves` de `account_payment.py`), el
      `foreign_debit/credit` del asiento de retención no cambia

## 2. Remoción en `l10n_ve_payment_extension`

- [ ] 2.1 Campos de `account.retention.line` sobrantes:
      `foreign_invoice_amount`, `foreign_iva_amount`,
      `foreign_invoice_total`. **Se conservan** `foreign_currency_id`
      (moneda del documento), `foreign_retention_amount`,
      `foreign_currency_rate` (los usa la modalidad indexada,
      ya aplicada en la rama de trabajo)
- [ ] 2.2 Campos de `account.retention`: `foreign_total_*`,
      `foreign_currency_id`; limpiar `_compute_totals`
- [ ] 2.3 `account.payment`: `retention_foreign_amount` y su compute
- [ ] 2.4 Ramas `not base_currency_is_vef` / USD en los cálculos de la línea.
      Hecho en `_compute_retention_amount`; pendiente `_compute_amounts`,
      `_compute_related_fields` (rama USD del ISLR acumulado) y
      `onchange_retention_amount`
- [ ] 2.5 Campo `base_currency_is_vef` y condiciones de vistas que dependen
      de él
- [ ] 2.6 Columnas y totales foreign en las vistas IVA, ISLR, municipal, la
      factura y el asistente de registro de pago
- [ ] 2.7 Ramas foreign de reportes (comprobante PDF, XLSX municipal, reporte
      de líneas, libros, asistente IVA)
- [ ] 2.8 Entradas de `i18n/es_VE.po` de los campos removidos

## 3. Remoción en otros módulos

- [x] 3.1 `l10n_ve_accountant`: eliminado
      `legacy_compute_line_ids_foreign_debit_and_credit`, su ayudante
      `get_invoice_line_ids_subtotals_by_name`, la acción de servidor
      `recompute_foreign_debit_and_credit_of_journal_entries` y su traducción
- [ ] 3.2 `l10n_ve_pos_mf`: rama `not vef_base` de `wizard_sales_book.py` que
      lee `foreign_retention_amount`
- [ ] 3.3 `binaural_mobile` (`integra-addons`): portal, controladores, JS y
      pruebas listados en el proposal

## 4. Verificación

- [ ] 4.1 Ajustar o eliminar las pruebas que afirman estos campos (lista en el
      proposal)
- [ ] 4.2 Suite completa del módulo y de `l10n_ve_accountant` en base
      descartable
- [ ] 4.3 Actualizar un entorno existente (`-u`) para comprobar que las
      columnas se eliminan sin errores

## 5. OpenSpec y proceso

- [x] 5.1 `proposal.md` con la evidencia y el alcance
- [ ] 5.2 Crear el ticket en helpdesk con este alcance y registrar aquí su id
- [ ] 5.3 Rama, commit y PR según la convención del repositorio (`ti`, desde
      `maintenance-19.0`)
