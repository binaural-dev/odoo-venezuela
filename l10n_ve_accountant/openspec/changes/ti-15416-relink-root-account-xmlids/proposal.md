# Fix: crear una sucursal cuando la raíz perdió xmlids de cuentas

## Why

Ticket #15416 (https://binaural.odoo.com/odoo/helpdesk/89/tickets/15416). Al crear
una sucursal, el plan de cuentas falla con
`External ID not found: account.<id_raiz>_account_activa_account_1122001`. La
sucursal resuelve con `ref()` las cuentas de la compañía raíz (`parent_ids[0]`)
y la raíz perdió (o dejó huérfanos) xmlids de cuentas del plan `ve`.

## What Changes

- `l10n_ve_accountant`: `account.chart.template._pre_load_data` (override) y el
  helper `_l10n_ve_relink_root_xmlids`. Solo para sucursales cuya raíz tiene el
  mismo plan: busca los xmlids de cuentas que la carga va a resolver
  (`property_*` del template y campos de `res.company`), detecta los
  faltantes/huérfanos y los re-vincula a la cuenta de la raíz con el código del plan.
- Tests: `l10n_ve_accountant/tests/test_chart_template_relink.py`.

## Decisiones

- **Nunca se crean cuentas.** Solo se restaura el xmlid de una cuenta existente
  (coincidencia exacta por código normalizado a `code_digits`, o única `{code}0*`).
- **Override de método privado del core** (`_pre_load_data`): es el único punto
  previo a `_post_load_data`, donde `ref()` falla. El contrato queda fijado en el
  test 09. TODO(20.0): revisar si el core ya repara estos xmlids.
- **Cuenta archivada:** se re-vincula igualmente, con un warning.
- **Alcance mínimo:** no toca cuentas de sistema/Outstanding, impuestos ni diarios.
- **Límite:** la recarga de una sucursal que ya tiene plan no se repara (el core
  descarta los `property_*` antes de `_pre_load_data`, y ahí el error no ocurre).

## Impacto a revisar

- En la instancia del ticket, crear la sucursal y confirmar los xmlids re-vinculados.
