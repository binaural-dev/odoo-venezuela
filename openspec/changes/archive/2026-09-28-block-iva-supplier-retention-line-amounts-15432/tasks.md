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

## 2b. Corrección de code review: campos alternos (`foreign_*`)

- [x] 2b.1 Mismo `readonly`/`force_save` agregado a
      `foreign_invoice_amount`, `foreign_iva_amount`,
      `foreign_invoice_total` y `foreign_retention_amount`
      (`account_retention_iva.xml:100-124`) -- son los mismos 4 montos,
      visibles cuando `base_currency_is_vef` es falso (compañía
      secundaria en multi-compañía cuya moneda no es VEF); quedaban sin
      el mismo tratamiento que sus contrapartes en Bs

## 3. Verificación

- [x] 3.1 Suite completa de `l10n_ve_payment_extension` corrida en
      contenedor Docker, base limpia, sin demo: 434 tests, sin fallos
      (antes y después del cambio)
- [x] 3.2 Re-corrida en contenedor Docker (instancia `ti15412-test`,
      mount directo sobre este checkout) tras 2b.1: 434 tests, sin
      fallos

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`ADDED` - capability nueva)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec`
      no disponible en este entorno)
- [x] 4.3 Corrección de code review: change archivado en
      `openspec/changes/archive/2026-09-28-<nombre>/` (convención de
      #1383) en vez de `l10n_ve_payment_extension/openspec/changes/`, y
      requirement fusionado en
      `openspec/specs/l10n_ve_payment_extension/spec.md`

## 5. Proceso

- [x] 5.1 Commit `[FIX] l10n_ve_accountant, l10n_ve_payment_extension:
      redondeo por linea y bloqueo de retencion IVA proveedores` en la
      rama
      `maint-19.0-ti-15432-fix-block-iva-providers-view-and-raunding-taxes-method`
      -- pusheado, PR #1390 abierto
- [ ] 5.2 Push del/los commit(s) de corrección de code review a `origin`
      (pendiente -- CI de `binauralbot` en el PR corresponde solo al
      commit `70482014d`, no a las correcciones posteriores)
