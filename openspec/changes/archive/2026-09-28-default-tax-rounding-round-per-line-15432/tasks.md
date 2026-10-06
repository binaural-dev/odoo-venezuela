# Tasks

## 1. Diagnóstico

- [x] 1.1 Confirmado que `tax_calculation_rounding_method` nace en
      `account/models/company.py` con `default='round_globally'`
- [x] 1.2 Confirmado que ningún módulo de `odoo-venezuela` sobreescribía
      ese default

## 2. Fix

- [x] 2.1 Override del default a `'round_per_line'` en
      `l10n_ve_accountant/models/res_company.py`
- [x] 2.2 Verificado en base de prueba (consulta directa a
      `res_company.tax_calculation_rounding_method`) que el override
      solo aplica a compañías nuevas -- la compañía principal (creada
      por `base`/`account` antes de que el override cargue en el
      registro) mantiene su valor previo (`round_globally`); por petición
      de los superiores, el encargado de la vertical (Saul Ortega)
      mantiene ese alcance (no se agrega migración retroactiva)

## 3. Verificación

- [x] 3.1 Test nuevo `test_55_new_company_defaults_to_round_per_line`
- [x] 3.2 Suite completa de `l10n_ve_accountant` corrida en contenedor
      Docker, base limpia, sin demo: 242 tests, sin fallos
- [x] 3.3 Misma suite corrida con `l10n_ve_invoice` instalado (vía
      `l10n_ve_payment_extension`, escenario real de producción): 242
      tests, sin fallos

## 3b. Corrección de code review (`test_31`)

- [x] 3b.1 `test_31` eliminado (no se admiten líneas negativas); se
      conserva `test_31b` con dos líneas positivas
- [x] 3b.2 Suite completa de `l10n_ve_accountant` en contenedor Docker,
      base limpia, sin demo: 300 tests, sin fallos

## 4. OpenSpec

- [x] 4.1 `proposal.md` + spec delta (`MODIFIED` -- reemplaza el
      requirement previo que documentaba esto como hallazgo sin
      resolver)
- [ ] 4.2 `openspec validate --changes` (no ejecutado: CLI `openspec`
      no disponible en este entorno)
- [x] 4.3 Corrección de code review: change archivado en
      `openspec/changes/archive/2026-09-28-<nombre>/` (convención de
      #1383) en vez de `l10n_ve_accountant/openspec/changes/`, y
      requirement fusionado en `openspec/specs/l10n_ve_accountant/spec.md`

## 5. Proceso

- [x] 5.1 Commit `[FIX] l10n_ve_accountant, l10n_ve_payment_extension:
      redondeo por linea y bloqueo de retencion IVA proveedores` en la
      rama
      `maint-19.0-ti-15432-fix-block-iva-providers-view-and-raunding-taxes-method`
      -- pusheado, PR #1390 abierto
- [ ] 5.2 Push del/los commit(s) de corrección de code review a `origin`
      (pendiente -- CI de `binauralbot` en el PR corresponde solo al
      commit `70482014d`, no a las correcciones posteriores)
