# Tasks

## 1. Diagnóstico

- [x] 1.1 Reproducido el `ValueError: Expected singleton` reportado en el ticket #15065, trazado hasta
      `account._force_default_sale_tax`/`_force_default_purchase_tax` haciendo `write()` en batch sobre
      2+ `product.template` a la vez durante `account.chart.template._post_load_data`
- [x] 1.2 Confirmado en el código real de `_enforce_single_tax_vals` que `records.name` y
      `records.company_id` son accesos escalares que disparan `ensure_one()` en Odoo 19 sobre un
      recordset multi-registro (`odoo/orm/fields.py:1655-1660`)
- [x] 1.3 Corregido el crash inicialmente y detectado un segundo defecto: `records.mapped(field_name)`
      calcula la unión de impuestos de TODO el batch, no el estado individual de cada producto
- [x] 1.4 Reproducido en producción/staging del cliente el falso positivo real: productos compartidos
      (`Iphone 17`, `PRODUCTO1`, `SERVICIO1`, `Standard delivery`, etc., todos con `company_id = False`)
      reportados con "2-3 taxes assigned" al crear una compañía nueva
- [x] 1.5 Confirmado que `account.tax.company_id` es obligatorio y NO `company_dependent`, y que
      `taxes_id`/`supplier_taxes_id` en `product.template` no tienen dominio por compañía — un producto
      compartido puede legítimamente acumular impuestos de varias compañías
- [x] 1.6 Revisada la tarea de deuda técnica [Integra 3.0] #81303 (originada en la revisión del PR
      `odoo-venezuela#1127`) y confirmado que describe los mismos dos defectos de raíz
- [x] 1.7 Detectado que el primer intento de fix se había construido sobre un commit local desactualizado
      de `maintenance-19.0` (anterior al merge del PR #1127), lo cual habría eliminado la exención de
      combo al mergearse — corregido reconstruyendo el fix sobre el HEAD real de `maintenance-19.0`

## 2. Fix

- [x] 2.1 `l10n_ve_accountant/models/product_template.py`: extraída `_apply_m2m_commands(current_ids,
      raw_value)` como función pura, reutilizada entre `create()` (baseline vacío) y `write()` (baseline
      de un registro)
- [x] 2.2 Nuevo método `_relevant_tax_ids(self, tax_ids, company)`: filtra ids de `account.tax` a los que
      pertenecen a `company` o un ancestro (`company.parent_ids`)
- [x] 2.3 `_enforce_single_tax_vals` separado en `_enforce_single_tax_vals_create` (sin cambios de
      comportamiento) y `_enforce_single_tax_vals_write` (reescrito)
- [x] 2.4 `_enforce_single_tax_vals_write` itera `for record in records:`, calculando `company` y
      baseline de impuestos por registro individual (no agregado)
- [x] 2.5 Inyección del impuesto por defecto: `Command.set` → `Command.link`, y de un único
      `records_to_validate.write(default_injections)` a un `write()` por campo escrito solo sobre el
      subset de productos que lo necesitan
- [x] 2.6 Nuevo método `_raise_fiscal_inconsistency(errors_by_record)`: agrupa errores por producto
      (`Product '%s':`) cuando hay 2+ afectados; formato plano si hay solo 1 (compatibilidad con tests
      existentes)
- [x] 2.7 Preservada íntegra la exención de combo y el comportamiento de FIX-060/061/062 ya mergeados en
      `maintenance-19.0` — confirmado por `git diff` que esas secciones no cambiaron de lógica

## 3. Tests

- [x] 3.1 `test_24_write_batch_multi_record_error_no_ensure_one_crash`: batch de 2+ productos no-combo
      reproduce el escenario del crash original y confirma `UserError` en vez de `ValueError`
- [x] 3.2 `test_25_write_batch_untouched_field_not_validated`: campo no presente en `vals`
      (`supplier_taxes_id`) no se valida usando baseline agregado
- [x] 3.3 `test_26_write_batch_only_offending_record_raises`: solo el producto realmente en conflicto
      aparece en el mensaje de error
- [x] 3.4 `test_27_write_batch_shared_product_ignores_other_company_taxes`: producto compartido con
      impuesto de otra compañía + link del default de la compañía actual → válido
- [x] 3.5 Confirmado que los 23 tests existentes (`test_01`-`test_23`, incluyendo todos los de combo)
      siguen pasando sin modificarlos

## 4. Verificación

- [x] 4.1 `./odoo test 19.0-tests-mig l10n_ve_accountant --tags=l10n_ve_accountant_core` (pool, base real
      de `maintenance-19.0`) → **52/52 tests, 0 failed, 0 error(s)**, cobertura 53%
- [x] 4.2 `./odoo test Sucursales-Miguel-New-V19 l10n_ve_accountant --tags=l10n_ve_accountant_core`
      (instancia real del cliente, fix puntual sobre su base histórica sin combo) → **42/42 tests, 0
      failed, 0 error(s)**, cobertura 54%
- [x] 4.3 Verificación manual en la instancia real del cliente (`odoo-Sucursales-Miguel-New-V19`, BD
      `sucursales-miguel-19`): usuario confirmó que la creación de compañía ya funciona
- [x] 4.4 Revisión de traducción: las 3 cadenas ya existentes no cambiaron de texto; se agregó a
      `es_VE.po` (pool y submódulo del cliente) la única cadena nueva, `Product '%s':`

## 5. Manifests

- [x] 5.1 `l10n_ve_accountant` (pool) `19.0.1.0.15` → `19.0.1.0.16`

## 6. Coordinación

- [x] 6.1 Documentado en el PR y en `proposal.md` el posible choque con
      `odoo-venezuela#1111` (`maint-19.0-ti-13828-fix-product-validation-taxes-regression`, agrega
      `company.unique_tax`, aún sin mergear, construido sobre una base anterior a este fix y al PR
      #1127) — requiere reconciliación manual al mergear ese PR
- [ ] 6.2 Reconciliar `company.unique_tax` (PR #1111) con la validación por producto individual y el
      filtrado por compañía de este fix, cuando ese PR se mergee (pendiente, no es responsabilidad de
      este cambio)

## 7. OpenSpec

- [x] 7.1 `proposal.md` + spec delta (`specs/product-batch-tax-validation/spec.md`)
- [x] 7.2 `openspec change validate l10n-ve-product-batch-tax-validation-fix` → "Change ... is valid"

## 8. Entregables

- [x] 8.1 PR pool: https://github.com/binaural-dev/odoo-venezuela/pull/1305
      (`maint-19.0-fix-ti-15065-error-in-create-company` → `maintenance-19.0`)
- [x] 8.2 PR cliente: https://github.com/binaural-consultoria/Sucursales-Miguel-New-V19/pull/6
      (`fix-ti-15065-error-in-create-company` → `staging`)
- [x] 8.3 Rama submódulo (cherry-pick puntual sobre base histórica del cliente): `fix-ti-15065-error-in-create-company`
