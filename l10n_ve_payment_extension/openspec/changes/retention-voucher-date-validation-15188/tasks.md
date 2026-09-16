# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el bug del ticket #15188: `date` (Fecha de
      Comprobante) se puede editar a una fecha anterior a la factura y
      `action_post()` lo acepta sin bloquear
- [x] 1.2 Confirmado que la validación existente
      (`_check_accounting_date_vs_invoices`, helpdesk #15019/#14984) solo
      compara `date_accounting`, nunca `date`
- [x] 1.3 Confirmado que `_check_dates_not_in_future` (límite superior, no
      futura) sí cubre ambos campos - el hueco es específico del límite
      inferior (no anterior a la factura) sobre `date`

## 2. Fix

- [x] 2.1 `_check_accounting_date_vs_invoices()`: agrega comparación de
      `date` contra `_get_max_invoice_date()`, mismo patrón que
      `date_accounting` (mensaje con la factura infractora)
- [x] 2.2 `@api.constrains("date_accounting", "date", "retention_line_ids")
      _check_accounting_date()`: agrega `date` a los campos que disparan
      el constraint
- [x] 2.3 Traducción del nuevo mensaje en `i18n/es_VE.po`

## 3. Verificación

- [x] 3.1 `test_voucher_date_earlier_than_invoice_blocks_helpdesk_15188`:
      `date` anterior a la factura bloquea con el mensaje correcto
- [x] 3.2 Mismo test: `date_accounting` anterior a la factura sigue
      bloqueando (no regresión sobre #15019/#14984)
- [x] 3.3 Mismo test: `date` igual a la fecha de la factura NO bloquea
      (límite inclusivo, igual que `date_accounting`)
- [x] 3.4 Suite completa del módulo corrida en aislado en contenedor
      Docker sobre base de datos descartable: 329 tests, 0 fallos

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`MODIFIED`, no `ADDED` - extiende el
      requisito existente de `retention-accounting-date-validation`)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec` no
      disponible en este entorno, igual que en el change anterior de esta
      misma capability)

## 5. Proceso (pendiente, no técnico)

- [x] 5.1 Commit `[FIX] l10n_ve_payment_extension: bloquea Fecha de
      Comprobante anterior a la factura (15188)` en la rama
      `maint-19.0-ti-14548-not-duplicate-concept-or-iva-retention`
- [ ] 5.2 Push a `origin` (pendiente de confirmación explícita)
