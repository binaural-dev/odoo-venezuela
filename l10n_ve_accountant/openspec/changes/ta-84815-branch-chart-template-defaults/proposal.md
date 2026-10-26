# Fix: crear una sucursal falla cuando el plan contable de la matriz no viene de la plantilla

## Metadata

| | |
|---|---|
| Change ID | `ta-84815-branch-chart-template-defaults` |
| Tarea | 84815 (Monfarmacia / Monbodegon) |
| Tipo | FIX |
| Módulo | `l10n_ve_accountant` |
| Rama base | `19.0` |

## Contexto

Al crear una sucursal (`res.company` con `parent_id`) de una compañía con `chart_template` definido, Odoo 19 carga la plantilla
sobre la sucursal. Uno de los pasos (`account.chart.template._post_load_data`) fija los valores por defecto de las cuentas
por cobrar y por pagar de los contactos de la sucursal, resolviendo el xmlid de la plantilla con la compañía **matriz**
(`account.<id_matriz>_<xmlid>`).

Una matriz cuyo plan contable no se cargó desde la plantilla (plan propio o migrado de otra versión) conserva
`chart_template = 've'` pero no tiene esos xmlids. Resultado real (Monfarmacia, staging):

```
ValueError: External ID not found in the system: account.2_account_activa_account_1122001
```

La creación completa hace rollback; no se puede crear la sucursal.

## Situación actual → esperada

| Caso | Hoy | Esperado |
|---|---|---|
| Sucursal de una matriz con plan propio (sin xmlids de plantilla) | Falla con `External ID not found` | Se crea; la sucursal toma las cuentas por defecto que ya tiene la matriz |
| Matriz sin valor por defecto para esa cuenta | Falla con `External ID not found` | Falla con un `UserError` claro (nombra el xmlid y la matriz) |
| Sucursal de una matriz con plan de plantilla | Se crea | Igual que hoy |
| Compañía sin padre | Se carga la plantilla | Igual que hoy |

## Por qué no se arregla en el core

El bucle que fija los defaults de propiedades vive en `account/models/chart_template.py` (`_post_load_data`). Para los campos de
`res.company` el propio core ya recupera el valor de la matriz cuando falla un `ref()` en una sucursal; este bucle es el único
sin ese respaldo. No se toca el core: se extiende el método desde la localización.

## Alcance

- Dentro: respaldo en ramas para los defaults de propiedad (`property_account_receivable_id`, `property_account_payable_id` y
  demás propiedades de `_get_property_accounts`) cuando el xmlid de la plantilla no existe.
- Fuera: propiedades de `res.company` (las resuelve el core); crear o vincular xmlids a las cuentas de la matriz; recargar la plantilla sobre una matriz migrada (duplica datos);
  la posición fiscal operativa de la sucursal (`binaural_operative_pos`).

## Approach

Sobrescribir `_post_load_data` en `l10n_ve_accountant`. Solo para sucursales: quitar del `template_data` las propiedades cuyo
xmlid no se resuelve, llamar al `super()` y copiar después, desde `ir.default`, el valor de la matriz. Si el default de la matriz es global
(sin compañía) no se copia nada, porque la sucursal ya lo recibe. Sin ninguno →
`UserError`.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Ocultar un error real de plantilla | Solo actúa en sucursales, solo para propiedades de cuenta y deja un `warning` en el log; sin default en la matriz falla |
| Método privado del core que cambie entre versiones | Cubierto por tests (incluye caso de extremo a extremo con creación real de la sucursal) |
| La matriz tiene el default de otra cuenta que la "esperada" por la plantilla | Es el comportamiento buscado: la sucursal hereda lo que el cliente ya configuró |

## Criterios de aceptación

- Crear una sucursal de una matriz sin xmlids de plantilla funciona y deja los mismos defaults que la matriz.
- Sin default en la matriz (ni global), el error nombra el xmlid, la matriz y el campo.
- Un default global de la matriz no bloquea la creación de la sucursal.
- Una matriz con plan de plantilla y las compañías sin padre no cambian de comportamiento.
- `TestBranchChartTemplateDefaults` pasa; sin el cambio, falla.
