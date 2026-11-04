# Spec delta: l10n_ve_accountant (ticket 15416)

## ADDED Requirements

### Requirement: Una sucursal debe poder crearse aunque la raíz haya perdido xmlids de cuentas

Al cargar el plan de cuentas en una sucursal, el sistema SHALL re-vincular los
xmlids de cuentas de la compañía raíz que la carga resuelve y que faltan o
quedaron huérfanos, buscando la cuenta de la raíz por el código del plan. El
sistema SHALL NOT crear cuentas.

#### Scenario: xmlid faltante

- **GIVEN** una raíz con plan `ve` a la que le falta el xmlid de una cuenta del plan
- **WHEN** se crea una sucursal
- **THEN** el xmlid SHALL quedar re-vinculado a la cuenta existente, sin crear cuentas

#### Scenario: xmlid huérfano

- **GIVEN** un xmlid de la raíz cuyo `res_id` apunta a una cuenta inexistente
- **WHEN** se crea una sucursal
- **THEN** el xmlid SHALL reemplazarse por la cuenta de la raíz con el código del plan

#### Scenario: Sin cuenta con ese código

- **GIVEN** un xmlid faltante y ninguna cuenta de la raíz con el código del plan
- **WHEN** se crea una sucursal
- **THEN** el sistema SHALL registrar un warning y la carga SHALL fallar como lo hace el core (`ValueError`)

#### Scenario: Varias coincidencias sin exacta

- **GIVEN** varias cuentas cuyo código coincide con `{code}0*` y ninguna con el código exacto
- **WHEN** se crea una sucursal
- **THEN** el sistema SHALL registrar un warning y SHALL NOT re-vincular ninguna

#### Scenario: Raíz con plan distinto o sin plan

- **GIVEN** una raíz sin plan o con un plan distinto al que se carga
- **WHEN** se crea una sucursal
- **THEN** el sistema SHALL NOT hacer nada (no-op)

#### Scenario: Alcance mínimo

- **WHEN** se re-vinculan xmlids
- **THEN** el sistema SHALL tocar solo cuentas referenciadas por `property_*` y campos de `res.company`, y SHALL NOT tocar cuentas de sistema/Outstanding, impuestos ni diarios

#### Scenario: Límite, recarga de una sucursal con plan

- **GIVEN** una sucursal que ya tiene el plan cargado
- **WHEN** se recarga el plan
- **THEN** el sistema SHALL NOT reparar xmlids de la raíz (el core no los resuelve en ese camino)
