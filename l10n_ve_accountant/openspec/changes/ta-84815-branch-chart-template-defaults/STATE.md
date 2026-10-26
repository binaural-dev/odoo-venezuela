# Estado y verificación

Fecha: 2026-10-26. Base: `origin/19.0` (e4413b234). Odoo 19.0 (enterprise), BD de control con la plantilla `ve` cargada nativamente.

## Comando reproducible
```bash
odoo -d <bd> -u l10n_ve_accountant --test-tags /l10n_ve_accountant:TestBranchChartTemplateDefaults --stop-after-init
odoo -d <bd> --test-tags /l10n_ve_accountant --stop-after-init        # suite completa del módulo
```
`<bd>`: base de datos con `account`, `sale`, `l10n_ve_accountant` instalados y la plantilla `ve` cargada en la compañía principal (el test de
extremo a extremo carga la plantilla `ve` en una compañía nueva).

| Verificación | Resultado |
|---|---|
| `TestBranchChartTemplateDefaults` con el cambio | 7/7 OK |
| Tests de default global y de propiedades de `res.company` con la versión anterior del código | Fallan (el código previo no los cubría) |
| Los 5 tests de la versión inicial contra `origin/19.0` sin el cambio | 4 fallan o dan error (3 fallos y 1 error, los que ejercitan la sucursal); el de "compañía raíz no afectada" pasa en ambos casos |
| Suite completa `l10n_ve_accountant` (362 tests) | 357 OK; 5 con fallo/error, todos en `TestProductTemplate` (test_14, 22, 23, 27, 30) |
| `TestProductTemplate` sin el cambio (`origin/19.0`) | Los mismos 5 fallan/dan error: preexistentes, no relacionados con este cambio |
| Reproducción real (Monfarmacia, copia de la BD de staging, plan propio sin xmlids) | Sin el cambio: `External ID not found: account.2_account_activa_account_1122001`. Con el cambio: sucursal creada con los defaults 741/779 igual que la matriz; matriz sin defaults → `UserError` claro |
| `scripts/precommit` de Binaural (módulo `l10n_ve_accountant`) | Pasa |

Pendiente: revisión de Producto, que entre al próximo tag de `odoo-venezuela`, y validar en el staging del cliente al subir el submódulo.
