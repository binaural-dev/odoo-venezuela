# Tasks

## 1. Diagnóstico

- [x] 1.1 Localizado el form compartido cliente/proveedor:
      `view_retention_iva_form_l10n_ve_payment_extension` en
      `account_retention_iva.xml`, usado por ambas acciones
      (`action_retention_iva_client` y `action_retention_iva_supplier`)
- [x] 1.2 Confirmado que los 4 campos de monto no tenían ninguna
      restricción de `readonly` ligada al `type` de la retención

## 2. Fix

- [x] 2.1 `readonly="parent.type in ('in_invoice', 'in_refund',
      'in_debit')"` + `force_save="1"` en `invoice_total`,
      `invoice_amount`, `iva_amount`, `retention_amount`

## 3. Verificación

- [x] 3.1 Suite completa de `l10n_ve_payment_extension` corrida en
      contenedor Docker, base limpia, sin demo: 434 tests, sin fallos
      (antes y después del cambio)

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`ADDED` - capability nueva)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec`
      no disponible en este entorno)

## 5. Proceso

- [x] 5.1 Commit `[FIX] l10n_ve_accountant, l10n_ve_payment_extension:
      redondeo por linea y bloqueo de retencion IVA proveedores` en la
      rama
      `maint-19.0-ti-15432-fix-block-iva-providers-view-and-raunding-taxes-method`
- [ ] 5.2 Push a `origin` (pendiente de confirmación explícita)
