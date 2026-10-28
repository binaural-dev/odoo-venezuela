# Estado y verificación

Fecha: 2026-10-28. Base: `origin/19.0`. Odoo 19.0 (enterprise).

## Comando reproducible
```bash
odoo -d <bd> -u l10n_ve_accountant --test-tags /l10n_ve_accountant:TestBranchChartTemplateDefaults --stop-after-init
odoo -d <bd> --test-tags /l10n_ve_accountant --stop-after-init        # suite completa del módulo
```
`<bd>`: cualquier base de datos con `l10n_ve_accountant` instalado (también una BD limpia: el test de extremo a extremo usa `generic_coa`).

| Verificación | Resultado |
|---|---|
| `TestBranchChartTemplateDefaults` en BD limpia sin `l10n_ve` (reproduce el CI) | 10/10 OK |
| Los mismos tests con la versión anterior del código del PR | Fallan los 3 que prueban el comportamiento nuevo (mensaje único, solo las faltantes, propiedad no obligatoria); el de "matriz sin `chart_template`" pasa en ambos casos porque fija que no hay regresión |
| Suite completa `l10n_ve_accountant` en BD nueva (365 tests) | 365 OK, 0 fallos, 0 errores |
| Primer CI del PR (BD limpia) | 1 error: el test de extremo a extremo llamaba a `try_loading('ve')` (instala `l10n_ve`, prohibido dentro de un test). Corregido usando `generic_coa` |
| Reproducción real (Monfarmacia, copia de la BD de staging, plan propio sin xmlids) | Sin el cambio: `External ID not found: account.2_account_activa_account_1122001`. Con el cambio: sucursal creada con los defaults 741/779 de la matriz; un contacto de la sucursal recibe esas cuentas; matriz sin default → `UserError` claro |
| `scripts/precommit` de Binaural (módulo `l10n_ve_accountant`) | Pasa |

Pendiente: revisión de Producto, que entre al próximo tag de `odoo-venezuela`, y validar en el staging del cliente al subir el submódulo.
